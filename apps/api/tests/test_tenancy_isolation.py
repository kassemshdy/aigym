"""The cross-tenant isolation suite decision 7 calls for: tenant isolation
is 'the highest-stakes correctness property in the product,' so it gets its
own file and its own CI job (see .github/workflows/ci.yml's `tenancy` job)
rather than being one assertion among many in a general test run.

Two layers, both required:
  1. API layer — every endpoint must treat another gym's ids as if they
     don't exist (404, or absent from a list), never leak a 403 that
     confirms the id is real.
  2. Database layer — the policy itself, exercised directly through the
     app's own runtime role (never the owner/migrations role, which is a
     superuser and bypasses Row-Level Security regardless of what the
     policy says).
"""

import itertools
import uuid
from datetime import UTC, datetime
from typing import NamedTuple

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db import get_sessionmaker, tenant_session
from app.models import Member

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_phone_counter = itertools.count(1)


def _next_phone() -> str:
    return f"+96178{next(_phone_counter):06d}"


class NewGym(NamedTuple):
    gym_id: uuid.UUID
    headers: dict[str, str]
    manager_phone: str


async def _new_gym(client: AsyncClient, *, slug: str) -> NewGym:
    manager_phone = _next_phone()
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_phone": manager_phone, "manager_pin": "1234",
        },
    )
    assert onboard.status_code == 201, onboard.text
    gym_id = uuid.UUID(onboard.json()["gym_id"])

    login = await client.post("/auth/staff/login", json={"phone": manager_phone, "pin": "1234"})
    token = login.json()["access_token"]
    return NewGym(gym_id, {"Authorization": f"Bearer {token}"}, manager_phone)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _insert_member(gym_id: uuid.UUID, *, phone: str) -> uuid.UUID:
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Isolation Test Member",
                phone=phone, joined_at=datetime.now(UTC),
            )
        )
    return member_id


class TwoGyms(NamedTuple):
    a: NewGym
    b: NewGym
    member_a: uuid.UUID
    member_b: uuid.UUID


@pytest.fixture
async def two_gyms(client: AsyncClient) -> TwoGyms:
    """Gym A and gym B, each with one manager and one member."""
    gym_a = await _new_gym(client, slug="isolation-a")
    gym_b = await _new_gym(client, slug="isolation-b")
    member_a = await _insert_member(gym_a.gym_id, phone=_next_phone())
    member_b = await _insert_member(gym_b.gym_id, phone=_next_phone())
    return TwoGyms(gym_a, gym_b, member_a, member_b)


async def test_member_list_never_shows_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    list_a = await client.get("/members", headers=two_gyms.a.headers)
    list_b = await client.get("/members", headers=two_gyms.b.headers)
    ids_a = {m["id"] for m in list_a.json()}
    ids_b = {m["id"] for m in list_b.json()}

    assert str(two_gyms.member_a) in ids_a
    assert str(two_gyms.member_b) not in ids_a
    assert str(two_gyms.member_b) in ids_b
    assert str(two_gyms.member_a) not in ids_b


async def test_get_member_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    cross = await client.get(f"/members/{two_gyms.member_b}", headers=two_gyms.a.headers)
    assert cross.status_code == 404

    reverse = await client.get(f"/members/{two_gyms.member_a}", headers=two_gyms.b.headers)
    assert reverse.status_code == 404


async def test_patch_member_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.patch(
        f"/members/{two_gyms.member_b}",
        headers=_idem(two_gyms.a.headers),
        json={"name_en": "Hijacked"},
    )
    assert response.status_code == 404


async def test_record_payment_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.post(
        f"/members/{two_gyms.member_b}/payments",
        headers=_idem(two_gyms.a.headers),
        json={"amount_usd": 999.0, "method": "cash"},
    )
    assert response.status_code == 404


async def test_check_in_404s_for_the_other_gym(client: AsyncClient, two_gyms: TwoGyms) -> None:
    response = await client.post(
        "/check-ins",
        headers=_idem(two_gyms.a.headers),
        json={"member_id": str(two_gyms.member_b)},
    )
    assert response.status_code == 404


async def test_whatsapp_reminder_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.get(
        f"/members/{two_gyms.member_b}/whatsapp-reminder", headers=two_gyms.a.headers
    )
    assert response.status_code == 404


async def test_lapsed_list_never_shows_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    lapsed = await client.get("/members/lapsed?min_days=0", headers=two_gyms.a.headers)
    assert str(two_gyms.member_b) not in {m["id"] for m in lapsed.json()}


async def test_payments_list_never_shows_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    plan_a = (await client.get("/plans", headers=two_gyms.a.headers)).json()[0]["id"]
    plan_b = (await client.get("/plans", headers=two_gyms.b.headers)).json()[0]["id"]

    payment_a = await client.post(
        f"/members/{two_gyms.member_a}/payments",
        headers=_idem(two_gyms.a.headers),
        json={"amount_usd": 50.0, "method": "cash", "plan_id": plan_a},
    )
    payment_b = await client.post(
        f"/members/{two_gyms.member_b}/payments",
        headers=_idem(two_gyms.b.headers),
        json={"amount_usd": 50.0, "method": "cash", "plan_id": plan_b},
    )
    assert payment_a.status_code == 200, payment_a.text
    assert payment_b.status_code == 200, payment_b.text

    payments_a = await client.get("/payments", headers=two_gyms.a.headers)
    member_ids_a = {p["member_id"] for p in payments_a.json()}
    assert str(two_gyms.member_a) in member_ids_a
    assert str(two_gyms.member_b) not in member_ids_a


async def test_plans_never_shows_the_other_gym(client: AsyncClient, two_gyms: TwoGyms) -> None:
    plans_a = {p["id"] for p in (await client.get("/plans", headers=two_gyms.a.headers)).json()}
    plans_b = {p["id"] for p in (await client.get("/plans", headers=two_gyms.b.headers)).json()}
    # Each gym's onboarding seeds its own starter plans; the sets must be disjoint.
    assert plans_a.isdisjoint(plans_b)


async def test_staff_login_never_crosses_gyms(client: AsyncClient) -> None:
    """A staff account belongs to the gym it was onboarded into. Logging in
    must never resolve to a different gym's id, even by coincidence of
    query ordering."""
    gym_a = await _new_gym(client, slug="isolation-login-a")
    gym_b = await _new_gym(client, slug="isolation-login-b")

    login_a = await client.post(
        "/auth/staff/login", json={"phone": gym_a.manager_phone, "pin": "1234"}
    )
    login_b = await client.post(
        "/auth/staff/login", json={"phone": gym_b.manager_phone, "pin": "1234"}
    )

    me_a = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login_a.json()['access_token']}"}
    )
    me_b = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login_b.json()['access_token']}"}
    )
    assert me_a.json()["gym_id"] == str(gym_a.gym_id)
    assert me_b.json()["gym_id"] == str(gym_b.gym_id)
    assert login_a.json()["access_token"] != login_b.json()["access_token"]


# --------------------------------------------------------------------------
# Database layer: exercised directly through the app's own runtime role
# (aigym_app, NOT the owner/migrations role — a superuser bypasses RLS
# regardless of policy, so testing through it would prove nothing).
# --------------------------------------------------------------------------


async def test_rls_blocks_cross_gym_select_at_the_database_layer(two_gyms: TwoGyms) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.gym_id', :gym_id, true)"),
            {"gym_id": str(two_gyms.a.gym_id)},
        )
        result = await session.execute(select(Member).where(Member.id == two_gyms.member_b))
        assert result.scalar_one_or_none() is None, (
            "gym A's connection could read gym B's member row directly — RLS is not enforcing"
        )


async def test_rls_blocks_query_with_no_gym_id_set_at_all(two_gyms: TwoGyms) -> None:
    """A connection that never calls set_config must fail closed — zero
    rows, not every gym's rows and not an error."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        result = await session.execute(select(Member))
        assert result.scalars().all() == []


async def test_rls_blocks_cross_gym_write_at_the_database_layer(two_gyms: TwoGyms) -> None:
    """WITH CHECK, not just USING: gym A's connection must not be able to
    insert a row claiming gym B's id, even though it knows gym B's id."""
    sessionmaker = get_sessionmaker()
    with pytest.raises(Exception, match="row-level security"):
        async with sessionmaker() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.gym_id', :gym_id, true)"),
                {"gym_id": str(two_gyms.a.gym_id)},
            )
            session.add(
                Member(
                    id=uuid.uuid4(), gym_id=two_gyms.b.gym_id, name="x", name_en="x",
                    phone=_next_phone(), joined_at=datetime.now(UTC),
                )
            )
            await session.flush()
