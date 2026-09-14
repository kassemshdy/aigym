"""Set or reset a staff member's login PIN.

Run this against a real database (locally or via `railway ssh -s api --
uv run python scripts/set_staff_pin.py`) whenever a manager or coach needs
a PIN set for the first time or reset after being forgotten — there is no
self-service flow for this yet (Phase 2 shipped phone+PIN login, not PIN
management).

Phone and PIN are prompted interactively, never taken as argv, so neither
ends up in shell history or a process list.

Connects with the migrations role (the table owner). staff_users carries no
RLS policy at all (decision 16's own documented exception — it's looked up
before any request has a gym_id), so the app role could write to it too, but
the owner connection is what seed.py already uses for the same class of
operation and keeping one convention for these one-off scripts is simpler.
"""

import asyncio
import getpass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import StaffUser
from app.security.hashing import hash_secret
from app.settings import get_settings


async def main() -> None:
    phone = input("Staff phone (e.g. +96170622211): ").strip()
    pin = getpass.getpass("New PIN: ").strip()
    confirm = getpass.getpass("Confirm PIN: ").strip()
    if pin != confirm:
        print("PINs did not match — nothing changed.")
        return
    if not pin:
        print("PIN cannot be empty — nothing changed.")
        return

    settings = get_settings()
    engine = create_async_engine(settings.database_url_migrations)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        staff = (
            await session.execute(select(StaffUser).where(StaffUser.phone == phone))
        ).scalar_one_or_none()
        if staff is None:
            print(f"No staff account found with phone {phone}.")
            return
        staff.pin_hash = hash_secret(pin)
        await session.commit()
        print(f"PIN set for {staff.name} ({phone}).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
