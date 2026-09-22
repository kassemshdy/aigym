import itertools
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import event, select

from app.db import get_engine, tenant_session
from app.models import Attendance, Subscription

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_phone_counter = itertools.count(1)


def _next_manager_username() -> str:
    return f"manager{next(_phone_counter)}"


async def _gym_and_staff_token(
    client: AsyncClient, *, slug: str
) -> tuple[uuid.UUID, dict[str, str]]:
    manager_username = _next_manager_username()
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": manager_username,
            "manager_password": "hunter22", "manager_phone": f"+96179{next(_phone_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    gym_id = uuid.UUID(onboard.json()["gym_id"])

    login = await client.post(
        "/auth/staff/login", json={"username": manager_username, "password": "hunter22"}
    )
    token = login.json()["access_token"]
    return gym_id, {"Authorization": f"Bearer {token}"}


def _idem(headers: dict[str, str]) -> dict[str, str]:
    """A fresh Idempotency-Key for one write — reusing the same key across
    two different request bodies is a 409 by design (test_idempotency.py),
    not a bug to route around here."""
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _get_a_plan_id(client: AsyncClient, headers: dict[str, str]) -> str:
    plans = await client.get("/plans", headers=headers)
    assert plans.status_code == 200
    return str(plans.json()[0]["id"])


def _member_payload(plan_id: str, phone: str) -> dict[str, Any]:
    return {
        "name": "عضو جديد", "name_en": "New Member", "phone": phone, "plan_id": plan_id,
        "goal": "health", "level": "new", "height_cm": 170, "weight_kg": 70.0,
        "body_fat": None, "injuries": [], "days_per_week": 3, "job": "desk", "sleep_hours": 7.0,
    }


async def test_create_and_get_member(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="members-a")
    plan_id = await _get_a_plan_id(client, headers)

    create = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174000001")
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["name_en"] == "New Member"
    assert body["dues"]["status"] == "paid"
    assert body["profile"]["goal"] == "health"

    fetched = await client.get(f"/members/{body['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["phone"] == "+96174000001"


async def test_lapsed_payment_clears_dues(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="members-b")
    plan_id = await _get_a_plan_id(client, headers)

    create = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174000002")
    )
    member_id = create.json()["id"]

    # Force the member's subscription into the past so dues shows 'due'.
    async with tenant_session(gym_id) as session:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.member_id == uuid.UUID(member_id))
            )
        ).scalar_one()
        sub.ends_at = datetime.now(UTC) - timedelta(days=5)

    lapsed_check = await client.get(f"/members/{member_id}", headers=headers)
    assert lapsed_check.json()["dues"]["status"] == "due"
    assert lapsed_check.json()["dues"]["owed_usd"] > 0

    payment = await client.post(
        f"/members/{member_id}/payments",
        headers=_idem(headers),
        json={"amount_usd": 35.0, "method": "cash"},
    )
    assert payment.status_code == 200, payment.text
    assert payment.json()["dues"]["status"] == "paid"


async def test_lapsed_members_endpoint(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="members-c")
    plan_id = await _get_a_plan_id(client, headers)

    never_visited = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174000003")
    )
    recently_visited = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174000004")
    )
    recent_id = recently_visited.json()["id"]

    async with tenant_session(gym_id) as session:
        session.add(
            Attendance(
                id=uuid.uuid4(), gym_id=gym_id, member_id=uuid.UUID(recent_id),
                date=datetime.now(UTC).date(),
            )
        )

    lapsed = await client.get("/members/lapsed?min_days=14", headers=headers)
    assert lapsed.status_code == 200
    lapsed_ids = {m["id"] for m in lapsed.json()}
    assert never_visited.json()["id"] in lapsed_ids
    assert recent_id not in lapsed_ids


async def test_whatsapp_reminder_composer(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="members-d")
    plan_id = await _get_a_plan_id(client, headers)
    create = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174000005")
    )
    member_id = create.json()["id"]

    reminder = await client.get(
        f"/members/{member_id}/whatsapp-reminder?lang=en", headers=headers
    )
    assert reminder.status_code == 200
    assert reminder.json()["wa_link"].startswith("https://wa.me/96174000005")


async def test_listing_members_does_not_scale_its_query_count_with_member_count(
    client: AsyncClient,
) -> None:
    """The regression guard for Phase 6 stage 1. GET /members used to run
    three queries per member (current subscription, its plan, last visit),
    so a gym growing from 5 to 300 members grew the request from ~15 to
    ~900 round trips. Asserting the *shape* — that adding members does not
    add queries — rather than an exact count, which would break on any
    unrelated middleware change.
    """
    _gym_id, headers = await _gym_and_staff_token(client, slug="members-f")
    plan_id = await _get_a_plan_id(client, headers)

    statements: list[str] = []

    @event.listens_for(get_engine().sync_engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    try:
        for i in range(2):
            await client.post(
                "/members",
                headers=_idem(headers),
                json=_member_payload(plan_id, f"+9617410{i:04d}"),
            )
        statements.clear()
        first = await client.get("/members", headers=headers)
        with_two = len(statements)

        for i in range(2, 8):
            await client.post(
                "/members",
                headers=_idem(headers),
                json=_member_payload(plan_id, f"+9617410{i:04d}"),
            )
        statements.clear()
        second = await client.get("/members", headers=headers)
        with_eight = len(statements)
    finally:
        event.remove(get_engine().sync_engine, "before_cursor_execute", _count)

    assert len(first.json()) == 2
    assert len(second.json()) == 8
    # Four times the members, identical query count.
    assert with_eight == with_two, f"{with_two} queries for 2 members, {with_eight} for 8"


async def test_list_payments(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="members-e")
    plan_id = await _get_a_plan_id(client, headers)
    create = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174000006")
    )
    member_id = create.json()["id"]

    await client.post(
        f"/members/{member_id}/payments",
        headers=_idem(headers),
        json={"amount_usd": 40.0, "method": "cash"},
    )

    payments = await client.get("/payments", headers=headers)
    assert payments.status_code == 200
    rows = payments.json()
    assert len(rows) == 1
    assert rows[0]["member_id"] == member_id
    assert rows[0]["amount_usd"] == 40.0
