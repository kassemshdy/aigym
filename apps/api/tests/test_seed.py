"""scripts/seed.py runs as the api service's Railway Pre-Deploy Command, on
every single deploy. That makes its production behaviour a data-safety
property, not a convenience: the demo path opens by deleting the gym, and
gyms.id cascades to every gym-scoped table, so running it against a real
gym would destroy every member, payment and logged set each time you shipped.

These tests pin the live path's three promises: it never destroys real
data, it never overwrites what the gym has since edited, and it clears the
sales-demo people a previous demo seed may have left behind.
"""

import importlib.util
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Member, Payment, Plan
from app.settings import get_settings

_SEED_PATH = Path(__file__).resolve().parent.parent / "scripts" / "seed.py"


def _seed_module():
    """scripts/ is not a package, so the script is loaded by path — the same
    way the Pre-Deploy Command invokes it."""
    spec = importlib.util.spec_from_file_location("seed_script", _SEED_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_script"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sessionmaker_and_seed():
    seed = _seed_module()
    engine = create_async_engine(get_settings().database_url_migrations)
    yield async_sessionmaker(engine, expire_on_commit=False), seed


async def test_the_live_path_keeps_real_data_and_drops_the_demo_people(
    sessionmaker_and_seed,
) -> None:
    sm, seed = sessionmaker_and_seed
    gym_id = seed.GYM_ID

    # Start from the demo dataset, as a database seeded before this change
    # would be.
    async with sm() as session:
        await seed.seed(session, demo=True)

    async with sm() as session:
        demo_members = (
            await session.execute(
                select(func.count()).select_from(Member).where(Member.gym_id == gym_id)
            )
        ).scalar_one()
        assert demo_members > 0, "the demo path should have seeded its fixtures"

        # A real member the front desk registered, with a real payment.
        real_id = uuid.uuid4()
        session.add(
            Member(
                id=real_id, gym_id=gym_id, name="زبون حقيقي", name_en="Real Walk-In",
                phone="+96176999111", joined_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            Payment(
                id=uuid.uuid4(), gym_id=gym_id, member_id=real_id, amount_usd=45.0,
                at=datetime.now(UTC), method="cash",
            )
        )
        # And a price the gym corrected for itself, as set_gym_plans writes.
        plan = (
            await session.execute(select(Plan).where(Plan.gym_id == gym_id).limit(1))
        ).scalars().first()
        assert plan is not None
        plan.price_usd = 17.5
        plan_id = plan.id
        await session.commit()

    # Two live seeds, because two deploys is where a destructive one bites.
    for _ in range(2):
        async with sm() as session:
            await seed.seed(session, demo=False)

    async with sm() as session:
        remaining = [
            m.name_en
            for m in (
                await session.execute(select(Member).where(Member.gym_id == gym_id))
            ).scalars()
        ]
        payments = (
            await session.execute(
                select(func.count()).select_from(Payment).where(Payment.gym_id == gym_id)
            )
        ).scalar_one()
        price = (
            await session.execute(select(Plan.price_usd).where(Plan.id == plan_id))
        ).scalar_one()

    assert remaining == ["Real Walk-In"], "demo people kept, or the real member was destroyed"
    assert payments == 1, "a real payment was destroyed by a deploy"
    assert float(price) == 17.5, "the seed clobbered a price the gym had corrected"


async def test_the_demo_path_refuses_to_repave_a_database_with_real_members(
    sessionmaker_and_seed,
) -> None:
    """The stop that does not depend on AIGYM_ENV being right. A wrong env
    var, a mistyped flag and a hand-run against production are the same
    accident, and all three have to end here rather than in a restore."""
    sm, seed = sessionmaker_and_seed
    gym_id = seed.GYM_ID

    async with sm() as session:
        await seed.seed(session, demo=False)
        session.add(
            Member(
                id=uuid.uuid4(), gym_id=gym_id, name="زبون حقيقي", name_en="Real Walk-In",
                phone="+96176999222", joined_at=datetime.now(UTC),
            )
        )
        await session.commit()

    async with sm() as session:
        with pytest.raises(seed.RealDataPresent, match="Refusing to repave"):
            await seed.seed(session, demo=True)

    # And the member is still there — the refusal happened before any delete.
    async with sm() as session:
        survivors = (
            await session.execute(
                select(func.count()).select_from(Member).where(Member.gym_id == gym_id)
            )
        ).scalar_one()
    assert survivors == 1


async def test_the_demo_path_still_repaves_its_own_fixtures(
    sessionmaker_and_seed,
) -> None:
    """The refusal must not block ordinary development: a database holding
    only this seed's own demo members is safe to repave, repeatedly."""
    sm, seed = sessionmaker_and_seed
    for _ in range(2):
        async with sm() as session:
            await seed.seed(session, demo=True)

    async with sm() as session:
        members = (
            await session.execute(
                select(func.count()).select_from(Member).where(Member.gym_id == seed.GYM_ID)
            )
        ).scalar_one()
    assert members == len(seed.MEMBER_ROWS)


async def test_the_live_path_bootstraps_configuration_on_an_empty_database(
    sessionmaker_and_seed,
) -> None:
    """A brand new gym still needs its plans, coaches and exercise catalog —
    "never overwrite" must not become "never create"."""
    sm, seed = sessionmaker_and_seed
    gym_id = seed.GYM_ID

    async with sm() as session:
        await seed.seed(session, demo=False)

    async with sm() as session:
        plans = (
            await session.execute(
                select(func.count()).select_from(Plan).where(Plan.gym_id == gym_id)
            )
        ).scalar_one()
        members = (
            await session.execute(
                select(func.count()).select_from(Member).where(Member.gym_id == gym_id)
            )
        ).scalar_one()

    assert plans > 0, "a new gym got no plans"
    assert members == 0, "the live path invented members on a fresh gym"
