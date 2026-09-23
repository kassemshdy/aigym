"""Set or reset a staff member's login password (decision 21: username +
password, not phone + PIN).

Run this against a real database (locally or via `railway ssh -s api --
uv run python scripts/set_staff_password.py`) whenever a staff account
needs a password set for the first time or reset after being forgotten.
There is also a self-service flow — POST /auth/staff/password/reset,
delivered over WhatsApp — this script is the operator-run fallback for
when that isn't set up or isn't working.

Username and password are prompted interactively, never taken as argv,
so neither ends up in shell history or a process list.

**On the `ops` service there is no terminal**, so a prompt would hang and
the deploy would sit there until it timed out. Set `AIGYM_SET_PASSWORD_USER`
and `AIGYM_SET_PASSWORD_VALUE` on that service and it runs without asking.
Those go in Railway's variable store, which is where a credential belongs —
unlike argv, which shows up in `ps`, and unlike a chat window or a ticket.
**Delete both variables once the run has succeeded**: nothing needs them
afterwards, and a password sitting in a service's environment is a password
that leaks with the next screenshot of that page.

Connects with the migrations role (the table owner). staff_users carries no
RLS policy at all (decision 16's own documented exception — it's looked up
before any request has a gym_id), so the app role could write to it too, but
the owner connection is what seed.py already uses for the same class of
operation and keeping one convention for these one-off scripts is simpler.
"""

import asyncio
import getpass
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import StaffUser
from app.security.hashing import hash_secret
from app.settings import get_settings


def credentials() -> tuple[str, str] | None:
    """From the environment when it is set, otherwise by prompting.

    The confirm step only exists for the interactive path: a variable you
    set deliberately cannot be mistyped twice the way a blind prompt can,
    and asking for it twice in a non-interactive run is a prompt that hangs.
    """
    username = os.environ.get("AIGYM_SET_PASSWORD_USER", "").strip()
    password = os.environ.get("AIGYM_SET_PASSWORD_VALUE", "")
    if username and password:
        print(f"Using AIGYM_SET_PASSWORD_USER={username} from the environment.")
        return username, password

    username = input("Staff username (e.g. kassem): ").strip()
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Confirm password: "):
        print("Passwords did not match — nothing changed.")
        return None
    return username, password


async def main() -> None:
    supplied = credentials()
    if supplied is None:
        return
    username, password = supplied
    if not password:
        print("Password cannot be empty — nothing changed.")
        return

    settings = get_settings()
    engine = create_async_engine(settings.database_url_migrations)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        staff = (
            await session.execute(select(StaffUser).where(StaffUser.username == username))
        ).scalar_one_or_none()
        if staff is None:
            print(f"No staff account found with username {username}.")
            return
        staff.password_hash = hash_secret(password)
        await session.commit()
        print(f"Password set for {staff.name} ({username}).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
