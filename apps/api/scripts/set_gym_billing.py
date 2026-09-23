"""Record what a gym has agreed to pay us, and what it has paid.

Tracked, never processed — decision 3's open question stays open because
Stripe does not serve Lebanese businesses. Money changes hands out of
band; this writes down what was agreed so "which gyms are past due" is
answerable without a spreadsheet living somewhere else.

Run it against a real database, locally or via
`railway ssh -s api -- uv run python scripts/set_gym_billing.py`. There
are HTTP routes for the same thing (GET/PATCH /gyms/{id}/billing behind
X-Onboarding-Secret), and this script exists for the same reason
set_staff_password.py does: at three to five pilot gyms, a prompt on a
terminal is the honest admin tool, and building a cross-gym UI for it
would be building a product nobody asked for.

**There is deliberately no way to reach this from the app.** `super_admin`
means owner of *one* gym (app/api/onboarding.py grants it to every gym's
first account), so any role check here would be one a customer passes on
their own billing row.

Connects with the migrations role, matching seed.py and
set_staff_password.py. `gyms` carries no RLS policy at all, so the app
role could do this too; one convention for these one-off scripts is
simpler than two.
"""

import asyncio
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.onboarding import BILLING_STATUSES
from app.models import Gym
from app.settings import get_settings


def _prompt_status(current: str) -> str | None:
    """None means leave it alone. An unrecognised value is refused rather
    than written, since nothing downstream would notice a typo."""
    raw = input(f"Status {BILLING_STATUSES} [{current}]: ").strip()
    if not raw:
        return None
    if raw not in BILLING_STATUSES:
        print(f"  '{raw}' is not one of {BILLING_STATUSES} — leaving it as {current}.")
        return None
    return raw


def _prompt_money(current: float | None) -> tuple[bool, float | None]:
    """(changed, value). '-' clears it, which a cancelled gym needs."""
    shown = "not set" if current is None else f"${current:g}"
    raw = input(f"Monthly USD, '-' to clear [{shown}]: ").strip()
    if not raw:
        return False, current
    if raw == "-":
        return True, None
    try:
        value = float(raw)
    except ValueError:
        print(f"  '{raw}' is not a number — leaving it as {shown}.")
        return False, current
    if value < 0:
        print("  A negative price is not a thing — leaving it alone.")
        return False, current
    return True, value


def _prompt_date(current: date | None) -> tuple[bool, date | None]:
    shown = "not set" if current is None else current.isoformat()
    raw = input(f"Paid through (YYYY-MM-DD), '-' to clear [{shown}]: ").strip()
    if not raw:
        return False, current
    if raw == "-":
        return True, None
    try:
        return True, date.fromisoformat(raw)
    except ValueError:
        print(f"  '{raw}' is not a date — leaving it as {shown}.")
        return False, current


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url_migrations)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        gyms = (await session.execute(select(Gym).order_by(Gym.slug))).scalars().all()
        if not gyms:
            print("No gyms on this database.")
            await engine.dispose()
            return

        print("\nGyms:")
        for row in gyms:
            row_paid = row.paid_through.isoformat() if row.paid_through else "—"
            row_price = f"${float(row.monthly_usd):g}" if row.monthly_usd is not None else "—"
            print(
                f"  {row.slug:24} {row.billing_status:10} {row_price:>8}"
                f"  paid through {row_paid}"
            )

        slug = input("\nWhich gym (slug)? ").strip()
        gym = next((g for g in gyms if g.slug == slug), None)
        if gym is None:
            print(f"No gym with slug {slug!r} — nothing changed.")
            await engine.dispose()
            return

        print(f"\nEditing {slug}. Blank keeps the current value.")
        status = _prompt_status(gym.billing_status)
        price_changed, price = _prompt_money(
            float(gym.monthly_usd) if gym.monthly_usd is not None else None
        )
        date_changed, paid_through = _prompt_date(gym.paid_through)
        notes = input(f"Notes [{gym.billing_notes or ''}]: ").strip()

        if status is not None:
            gym.billing_status = status
        if price_changed:
            gym.monthly_usd = price
        if date_changed:
            gym.paid_through = paid_through
        if notes:
            gym.billing_notes = notes

        summary = (
            f"{gym.billing_status}, "
            f"{f'${float(gym.monthly_usd):g}' if gym.monthly_usd is not None else 'no price'}, "
            f"paid through {gym.paid_through.isoformat() if gym.paid_through else '—'}"
        )
        if input(f"\nSave? {slug}: {summary}  [y/N] ").strip().lower() != "y":
            print("Nothing changed.")
            await engine.dispose()
            return

        await session.commit()
        print(f"Saved. {slug}: {summary}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
