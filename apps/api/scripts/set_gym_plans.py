"""Set a gym's real membership prices, interactively.

A gym onboarded through POST /gyms (or seeded) gets the three starter plans
from onboarding.py — $30 / $80 / $280 — which are placeholders, not any real
gym's prices. Until Phase 6 stage 7 gives managers a plans screen, this is
how a pilot gym's actual prices get set:

    railway ssh -s api -- uv run python scripts/set_gym_plans.py

This matters more than a cosmetic number. Dues are derived from
plans.price_usd (app/domain/dues.py, decision 17) and never stored, so every
figure the product is sold on — what a member owes, what the gym is owed,
the collection rate on the owner dashboard — is computed from these values.
Wrong prices here do not look wrong; they quietly make every downstream
number wrong.

Lists the gym's current plans, then prompts for a new price per plan.
Pressing enter leaves a plan unchanged, so this is safe to re-run and safe
to abandon halfway. Renaming and adding plans are deliberately out of scope:
this is the one field that silently corrupts arithmetic.

Connects with the migrations role, the same convention as seed.py and
set_staff_password.py for these one-off operator scripts.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Gym, Plan
from app.settings import get_settings


def _prompt_price(label: str, current: float) -> float | None:
    """None means "leave it alone" — an empty line, or anything that isn't a
    sane positive number. Refusing bad input beats writing a price nobody
    meant, given what reads these values."""
    raw = input(f"  {label} — currently ${current:g}. New price (enter to keep): ").strip()
    if not raw:
        return None
    try:
        price = float(raw.lstrip("$"))
    except ValueError:
        print(f"    '{raw}' is not a number — keeping ${current:g}.")
        return None
    if price <= 0:
        print(f"    A price must be above zero — keeping ${current:g}.")
        return None
    return round(price, 2)


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url_migrations)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        gyms = list((await session.execute(select(Gym).order_by(Gym.slug))).scalars())
        if not gyms:
            print("No gyms on this database.")
            return

        if len(gyms) == 1:
            gym = gyms[0]
            print(f"Gym: {gym.name.get('en', gym.slug)} ({gym.slug})")
        else:
            print("Gyms on this database:")
            for g in gyms:
                print(f"  {g.slug} — {g.name.get('en', g.slug)}")
            slug = input("Which gym (slug): ").strip()
            match = next((g for g in gyms if g.slug == slug), None)
            if match is None:
                print(f"No gym with slug {slug!r}.")
                return
            gym = match

        plans = list(
            (
                await session.execute(
                    select(Plan).where(Plan.gym_id == gym.id).order_by(Plan.price_usd)
                )
            ).scalars()
        )
        if not plans:
            print("This gym has no plans — onboarding should have created three.")
            return

        print(f"\n{len(plans)} plan(s). Press enter to leave a price unchanged.\n")
        changed = []
        for plan in plans:
            label = f"{plan.name.get('en', '?')} ({plan.days} days)"
            new_price = _prompt_price(label, float(plan.price_usd))
            if new_price is not None and new_price != float(plan.price_usd):
                changed.append((label, float(plan.price_usd), new_price))
                plan.price_usd = new_price

        if not changed:
            print("\nNothing changed.")
            return

        print("\nAbout to write:")
        for label, was, now in changed:
            print(f"  {label}: ${was:g} -> ${now:g}")
        if input("Apply? [y/N]: ").strip().lower() != "y":
            print("Nothing changed.")
            return

        await session.commit()
        print(f"\nUpdated {len(changed)} price(s) for {gym.name.get('en', gym.slug)}.")
        print("Existing members keep the price they were charged; dues recompute from now on.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
