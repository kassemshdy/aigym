"""A plan's price edit must not restate what the past owed or collected.

The bug these cover: every money figure used to resolve a price by joining
to `plans` *now*, so a gym raising its monthly plan from $30 to $45 also
raised what a member who lapsed in March was recorded as owing, and what
last quarter's dashboard said it had collected. Those figures are what the
sales guarantee is settled on, so they have to describe what happened
rather than the current price list. Decision 42.

Each test edits a plan's price *after* a period was sold under it, and
asserts the figure did not move.
"""

import itertools
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.db import tenant_session
from app.models import Subscription

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _gym(client: AsyncClient, slug: str) -> tuple[uuid.UUID, dict[str, str]]:
    username = f"snapshot{next(_counter)}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": username,
            "manager_password": "hunter22", "manager_phone": f"+96178{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    return uuid.UUID(onboard.json()["gym_id"]), {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


async def _plan(client: AsyncClient, headers: dict[str, str], price: float, days: int = 30) -> str:
    created = await client.post(
        "/plans",
        headers=_idem(headers),
        json={"name": {"ar": "شهري", "en": "Monthly"}, "price_usd": price, "days": days},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def _member_payload(plan_id: str, phone: str) -> dict[str, object]:
    return {
        "name": "عضو", "name_en": "Member", "phone": phone, "plan_id": plan_id,
        "goal": "health", "level": "beginner", "height_cm": 175, "weight_kg": 80.0,
        "days_per_week": 3, "job": "desk", "sleep_hours": 7.0, "injuries": [],
    }


async def _lapse(gym_id: uuid.UUID, member_id: str, *, days_ago: int) -> None:
    """Move the member's latest period into the past so it reads as lapsed.

    Shifts `starts_at` with `ends_at` rather than only the end. Moving the
    end alone produces a period that finished before it began, which no
    code path can create and which made an earlier version of this suite
    report $180 owed where $30 was right.
    """
    async with tenant_session(gym_id) as session:
        sub = (
            await session.execute(
                select(Subscription)
                .where(Subscription.member_id == uuid.UUID(member_id))
                .order_by(Subscription.ends_at.desc())
            )
        ).scalars().first()
        assert sub is not None
        sold = sub.ends_at - sub.starts_at
        sub.ends_at = datetime.now(UTC) - timedelta(days=days_ago)
        sub.starts_at = sub.ends_at - sold


async def test_a_period_records_the_price_it_was_sold_at(client: AsyncClient) -> None:
    gym_id, headers = await _gym(client, "snap-a")
    plan_id = await _plan(client, headers, 30.0)
    created = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174100001")
    )
    member_id = created.json()["id"]

    async with tenant_session(gym_id) as session:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.member_id == uuid.UUID(member_id))
            )
        ).scalar_one()
        assert float(sub.price_usd) == 30.0


async def test_raising_a_plan_does_not_change_what_a_lapsed_member_owes(
    client: AsyncClient,
) -> None:
    """The headline case. A member lapsed one cycle under a $30 plan owes
    $30 — including after the gym starts charging $45 for new sign-ups."""
    gym_id, headers = await _gym(client, "snap-b")
    plan_id = await _plan(client, headers, 30.0)
    created = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174100002")
    )
    member_id = created.json()["id"]
    await _lapse(gym_id, member_id, days_ago=5)

    before = await client.get(f"/members/{member_id}", headers=headers)
    assert before.json()["dues"] == {"status": "due", "owed_usd": 30.0}

    raised = await client.patch(
        f"/plans/{plan_id}", headers=_idem(headers), json={"price_usd": 45.0}
    )
    assert raised.status_code == 200, raised.text

    after = await client.get(f"/members/{member_id}", headers=headers)
    assert after.json()["dues"] == {"status": "due", "owed_usd": 30.0}


async def test_a_renewal_after_the_rise_is_charged_the_new_price(client: AsyncClient) -> None:
    """The other half: the snapshot must not freeze a member at an old
    price forever. The period sold *after* the rise costs the new price."""
    gym_id, headers = await _gym(client, "snap-c")
    plan_id = await _plan(client, headers, 30.0)
    created = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174100003")
    )
    member_id = created.json()["id"]
    await _lapse(gym_id, member_id, days_ago=5)

    await client.patch(f"/plans/{plan_id}", headers=_idem(headers), json={"price_usd": 45.0})
    paid = await client.post(
        f"/members/{member_id}/payments",
        headers=_idem(headers),
        json={"amount_usd": 45.0, "method": "cash"},
    )
    assert paid.status_code == 200, paid.text

    async with tenant_session(gym_id) as session:
        prices = sorted(
            float(s.price_usd)
            for s in (
                await session.execute(
                    select(Subscription).where(Subscription.member_id == uuid.UUID(member_id))
                )
            ).scalars()
        )
        assert prices == [30.0, 45.0]

    # And the new period, once lapsed, owes the new price.
    await _lapse(gym_id, member_id, days_ago=2)
    now_owed = await client.get(f"/members/{member_id}", headers=headers)
    assert now_owed.json()["dues"]["owed_usd"] == 45.0


async def test_raising_a_plan_does_not_restate_what_was_collected(client: AsyncClient) -> None:
    """The dashboard figure the guarantee is settled on. A period that fell
    due and was renewed inside the window is worth what it was sold for,
    whatever the plan costs by the time anyone looks at the report."""
    gym_id, headers = await _gym(client, "snap-d")
    plan_id = await _plan(client, headers, 30.0)
    created = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, "+96174100004")
    )
    member_id = created.json()["id"]
    await _lapse(gym_id, member_id, days_ago=5)
    await client.post(
        f"/members/{member_id}/payments",
        headers=_idem(headers),
        json={"amount_usd": 30.0, "method": "cash"},
    )

    before = await client.get("/analytics/summary?weeks=12", headers=headers)
    assert before.status_code == 200, before.text
    collected_before = before.json()["collection"]["collected_usd"]
    assert collected_before == 30.0

    await client.patch(f"/plans/{plan_id}", headers=_idem(headers), json={"price_usd": 45.0})

    after = await client.get("/analytics/summary?weeks=12", headers=headers)
    assert after.json()["collection"]["collected_usd"] == collected_before
