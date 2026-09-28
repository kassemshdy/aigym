"""Registering a member records whether they paid for their first period.

Reported from the live app: a member added at the desk showed "Paid" with
no payment anywhere in their history, and the dashboard said $0 collected.
The first period was granted paid-through with nothing behind it; recording
the fee afterwards then stacked a *second* period on top, so the member got
two for the price of one. Decision 48.
"""

import itertools
import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.db import tenant_session
from app.models import Payment, Subscription

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


async def _gym(client: AsyncClient, slug: str) -> tuple[uuid.UUID, dict[str, str]]:
    username = f"joinpay{next(_counter)}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": username,
            "manager_password": "hunter22", "manager_phone": f"+96176{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    return uuid.UUID(onboard.json()["gym_id"]), {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _plan(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    plans = await client.get("/plans", headers=headers)
    return dict(plans.json()[0])


def _payload(plan_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "name": "عضو", "name_en": "Member", "phone": f"+96176{next(_counter):06d}",
        "plan_id": plan_id, "goal": "health", "level": "new", "height_cm": 170,
        "weight_kg": 70.0, "injuries": [], "days_per_week": 3, "job": "desk",
        "sleep_hours": 7.0, **extra,
    }


async def _money(gym_id: uuid.UUID, member_id: str) -> tuple[list[Payment], list[Subscription]]:
    async with tenant_session(gym_id) as session:
        payments = list(
            (
                await session.execute(
                    select(Payment).where(Payment.member_id == uuid.UUID(member_id))
                )
            ).scalars()
        )
        periods = list(
            (
                await session.execute(
                    select(Subscription)
                    .where(Subscription.member_id == uuid.UUID(member_id))
                    .order_by(Subscription.ends_at)
                )
            ).scalars()
        )
    return payments, periods


async def test_paid_at_the_desk_is_a_payment_behind_the_paid_badge(client: AsyncClient) -> None:
    gym_id, headers = await _gym(client, "joinpay-a")
    plan = await _plan(client, headers)

    created = await client.post(
        "/members", headers=_idem(headers), json=_payload(plan["id"], payment_method="transfer")
    )
    assert created.status_code == 201, created.text
    assert created.json()["dues"]["status"] == "paid"

    payments, periods = await _money(gym_id, created.json()["id"])
    assert [(float(p.amount_usd), p.method) for p in payments] == [
        (float(plan["price_usd"]), "transfer")
    ]
    assert payments[0].recorded_by_staff_id is not None, "who took the money is on record"
    assert len(periods) == 1, "one payment, one period — not a renewal on top"


async def test_cash_is_the_default_because_that_is_what_the_desk_does(
    client: AsyncClient,
) -> None:
    gym_id, headers = await _gym(client, "joinpay-b")
    plan = await _plan(client, headers)

    created = await client.post("/members", headers=_idem(headers), json=_payload(plan["id"]))
    assert created.status_code == 201, created.text

    payments, _ = await _money(gym_id, created.json()["id"])
    assert [p.method for p in payments] == ["cash"]


async def test_not_paid_yet_owes_the_plan_price_from_today(client: AsyncClient) -> None:
    gym_id, headers = await _gym(client, "joinpay-c")
    plan = await _plan(client, headers)

    created = await client.post(
        "/members", headers=_idem(headers), json=_payload(plan["id"], payment_method="unpaid")
    )
    assert created.status_code == 201, created.text
    member_id = created.json()["id"]
    assert created.json()["dues"] == {"status": "due", "owed_usd": float(plan["price_usd"])}

    payments, _ = await _money(gym_id, member_id)
    assert payments == []

    # Paying later grants exactly one period, starting the day they paid.
    paid = await client.post(
        f"/members/{member_id}/payments",
        headers=_idem(headers),
        json={"amount_usd": plan["price_usd"], "method": "cash"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["dues"]["status"] == "paid"

    payments, periods = await _money(gym_id, member_id)
    assert len(payments) == 1
    granted = periods[-1].ends_at - periods[-1].starts_at
    assert granted.days == plan["days"]
    # The unpaid join is a period that ended the moment it began: nothing
    # was sold, so nothing was given.
    assert periods[0].ends_at == periods[0].starts_at


async def test_an_unknown_payment_method_is_refused(client: AsyncClient) -> None:
    _gym_id, headers = await _gym(client, "joinpay-d")
    plan = await _plan(client, headers)

    created = await client.post(
        "/members", headers=_idem(headers), json=_payload(plan["id"], payment_method="card")
    )
    assert created.status_code == 422, created.text


async def test_the_home_figure_counts_money_taken_on_joining(client: AsyncClient) -> None:
    """The second half of the report: "$0 collected" beside a member who
    just paid. `collection` measures renewals and rightly reads $0 here;
    `taken_usd` is the money that actually came in."""
    _gym_id, headers = await _gym(client, "joinpay-e")
    plan = await _plan(client, headers)

    await client.post("/members", headers=_idem(headers), json=_payload(plan["id"]))
    await client.post(
        "/members", headers=_idem(headers), json=_payload(plan["id"], payment_method="unpaid")
    )

    summary = await client.get("/analytics/summary?weeks=12", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["taken_usd"] == float(plan["price_usd"])
    assert body["taken_usd_previous"] == 0.0
    # The guarantee number is untouched: no renewal has happened yet.
    assert body["collection"]["collected_usd"] == 0.0
