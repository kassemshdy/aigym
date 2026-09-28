"""A removed staff member's username stayed taken forever, and invisible.

Reported from the live app: adding a manager answered "it exists", and the
staff list showed nobody by that name. Both were correct. `staff_users` is
not gym-scoped (decision 16), so the uniqueness check sees every gym;
`staff_gym_roles` is, so the list sees one. Removing someone deletes only
the second — on purpose, so a coach who also works at another gym is not
deleted there too — which leaves the account holding a name the gym can
neither see nor reuse.

These pin the behaviour that was wrong, the reason the account cannot
simply be deleted, and the release that gives the name back. Decision 45.
"""

import importlib.util
import itertools
import sys
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import StaffGymRole, StaffUser
from app.settings import get_settings

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "staff_accounts.py"


def _script():
    """scripts/ is not a package, so load by path — test_seed.py's pattern."""
    spec = importlib.util.spec_from_file_location("staff_accounts_script", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["staff_accounts_script"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sessionmaker():
    engine = create_async_engine(get_settings().database_url_migrations)
    yield async_sessionmaker(engine, expire_on_commit=False)


async def _gym_admin(client: AsyncClient, slug: str) -> dict[str, str]:
    username = f"owner{next(_counter)}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Owner", "manager_username": username,
            "manager_password": "hunter22", "manager_phone": f"+96178{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


def _coach(username: str) -> dict[str, str]:
    return {
        "username": username, "password": "hunter22", "name": "Assaf",
        "phone": f"+96179{next(_counter):06d}", "role": "coach",
    }


async def test_a_removed_staff_member_leaves_their_username_taken_and_invisible(
    client: AsyncClient,
) -> None:
    """The reported bug, exactly: taken by the check, absent from the list."""
    headers = await _gym_admin(client, "release-a")

    created = await client.post("/staff", headers=_idem(headers), json=_coach("assaf"))
    assert created.status_code == 201, created.text
    staff_id = created.json()["id"]

    removed = await client.delete(f"/staff/{staff_id}", headers=_idem(headers))
    assert removed.status_code in (200, 204), removed.text

    listed = await client.get("/staff", headers=headers)
    assert "assaf" not in [s["username"] for s in listed.json()], "should be off the roster"

    again = await client.post("/staff", headers=_idem(headers), json=_coach("assaf"))
    assert again.status_code == 409
    # The message has to name the thing the manager can act on, or they are
    # left exactly where this bug report started.
    assert "different one" in again.json()["detail"]


async def test_the_account_survives_removal_so_history_stays_attributed(
    client: AsyncClient, sessionmaker
) -> None:
    """Every reference to a staff member is ON DELETE SET NULL — payments
    recorded, drafts approved, sessions run. Deleting the account would
    blank all of it, which is why removal keeps the row."""
    headers = await _gym_admin(client, "release-b")
    created = await client.post("/staff", headers=_idem(headers), json=_coach("assaf2"))
    staff_id = uuid.UUID(created.json()["id"])
    await client.delete(f"/staff/{staff_id}", headers=_idem(headers))

    async with sessionmaker() as session:
        user = await session.get(StaffUser, staff_id)
        assert user is not None, "the account must outlive the access"
        roles = (
            await session.execute(
                select(StaffGymRole).where(StaffGymRole.staff_user_id == staff_id)
            )
        ).scalars().all()
        assert roles == [], "but hold no access anywhere"


def test_a_released_username_keeps_the_name_readable_and_cannot_collide() -> None:
    script = _script()
    first = script.released_username("assaf")
    second = script.released_username("assaf")
    assert first.startswith("assaf."), first
    assert first != second, "two releases of one name must not collide"


async def test_releasing_the_username_lets_the_name_be_used_again(
    client: AsyncClient, sessionmaker
) -> None:
    headers = await _gym_admin(client, "release-c")
    created = await client.post("/staff", headers=_idem(headers), json=_coach("assaf3"))
    staff_id = uuid.UUID(created.json()["id"])
    await client.delete(f"/staff/{staff_id}", headers=_idem(headers))

    script = _script()
    async with sessionmaker() as session:
        orphan = await session.get(StaffUser, staff_id)
        assert orphan is not None
        orphan.username = script.released_username(orphan.username)
        await session.commit()

    reused = await client.post("/staff", headers=_idem(headers), json=_coach("assaf3"))
    assert reused.status_code == 201, reused.text
    # A new account, not the old one resurrected — the old id still carries
    # whatever that person did while they worked here.
    assert uuid.UUID(reused.json()["id"]) != staff_id

    async with sessionmaker() as session:
        assert await session.get(StaffUser, staff_id) is not None
