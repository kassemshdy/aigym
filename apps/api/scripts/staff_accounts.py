"""Show who has a staff account, where they work, and free a burned username.

**The problem this exists for.** `staff_users.username` is unique across the
whole platform (decision 16: the table carries no RLS, because staff login
has to find the row before any gym is known). Access to a gym is a separate
row in `staff_gym_roles`, and `DELETE /staff/{id}` removes only that,
keeping the account — deliberately, so revoking a coach at one gym does not
delete them at the gym they also work at.

The consequence nobody wrote down: once someone is removed, their username
stays taken forever. `POST /staff` checks the global table and answers 409
"Username already taken"; the staff list joins to the gym-scoped table and
shows nothing. From the manager's side the name is simultaneously taken and
invisible, with no way back. Decision 45.

**Why a script rather than an endpoint.** Deciding whether a username can be
freed means asking "does this person hold a role at *any* gym", which is the
exact cross-gym read `staff_gym_roles`' RLS policy exists to block. Doing it
in a request would need a second call site for `get_owner_sessionmaker()`,
which decision 18 pins to staff login alone. A script connects as the
migrations role, where that read is legitimate and already the convention
(seed.py, set_gym_plans.py, set_staff_password.py). At a handful of gyms an
operator script is the honest tool — decision 36's reasoning again.

    # what accounts exist, and which are orphaned
    AIGYM_OPS_COMMAND="python scripts/staff_accounts.py"

    # free one, so the name can be used again
    AIGYM_OPS_COMMAND="python scripts/staff_accounts.py --release assaf"
    # or, where there is no terminal to pass arguments on:
    AIGYM_RELEASE_STAFF_USERNAME=assaf

**Nothing is ever deleted.** Releasing renames the account and leaves the row
and its id alone, because every historical reference to a staff member is
ON DELETE SET NULL — payments recorded, AI drafts approved, sessions run,
content uploaded. Deleting the account would silently blank "who took this
money" across the gym's whole history. An orphaned account cannot log in
anyway (`staff_login` answers 403 "This account has no gym access" when it
resolves no roles), so the username is the only thing of value left in it.
"""

import argparse
import asyncio
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Gym, StaffGymRole, StaffUser
from app.settings import get_settings

#: Long enough that two releases of the same name cannot collide, short
#: enough to stay readable in a database client.
SUFFIX_LENGTH = 6


def released_username(username: str) -> str:
    return f"{username}.released.{uuid.uuid4().hex[:SUFFIX_LENGTH]}"


def wanted_release() -> str | None:
    """--release, or the environment variable the `ops` service uses.

    A Railway deploy has no terminal, so anything that has to run there
    takes its input from the environment — the same shape
    set_staff_password.py uses.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", metavar="USERNAME", default=None)
    args = parser.parse_args()
    if args.release:
        return str(args.release)
    from_env = os.environ.get("AIGYM_RELEASE_STAFF_USERNAME", "").strip()
    return from_env or None


async def main() -> None:
    target = wanted_release()
    engine = create_async_engine(get_settings().database_url_migrations)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        gym_names = {
            gym.id: gym.slug for gym in (await session.execute(select(Gym))).scalars().all()
        }
        users = (
            await session.execute(select(StaffUser).order_by(StaffUser.username))
        ).scalars().all()
        roles = (await session.execute(select(StaffGymRole))).scalars().all()

        where: dict[uuid.UUID, list[str]] = {}
        for role in roles:
            slug = gym_names.get(role.gym_id, str(role.gym_id))
            where.setdefault(role.staff_user_id, []).append(f"{slug}:{role.role}")

        print(f"{len(users)} staff account(s)\n")
        width = max((len(u.username) for u in users), default=0)
        orphans = []
        for user in users:
            held = where.get(user.id, [])
            if not held:
                orphans.append(user)
            print(f"  {user.username:<{width}}  {', '.join(held) or '— no gym access —'}")

        if orphans:
            print(
                f"\n{len(orphans)} account(s) hold no access anywhere. They cannot log in, "
                "and their usernames cannot be reused until released:"
            )
            for user in orphans:
                print(f"  {user.username}")
            print("\n  python scripts/staff_accounts.py --release <username>")

        if target is None:
            print("\nNothing released — pass --release to free a username.")
            await engine.dispose()
            return

        match = next((u for u in users if u.username == target), None)
        if match is None:
            print(f"\nNo staff account with username {target!r}.")
            await engine.dispose()
            return
        held = where.get(match.id, [])
        if held:
            # Renaming someone who still works somewhere would break the
            # login they use every day, and the username is how they log in.
            print(
                f"\nRefusing: {target!r} still has access at {', '.join(held)}. "
                "Remove their access first, or pick a different username."
            )
            await engine.dispose()
            return

        freed = released_username(match.username)
        match.username = freed
        await session.commit()
        print(f"\nReleased {target!r} → {freed}")
        print(f"  account id {match.id} kept, so their history stays attributed.")
        print(f"  {target!r} can now be used for a new account.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
