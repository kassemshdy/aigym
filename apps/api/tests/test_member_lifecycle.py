"""A member who left must stop counting, without being erased.

Before decision 43 nothing could record a departure, so someone who quit
stayed on the roster forever: still in the lapsed list, still accruing dues
against a plan they had cancelled, still counted as active. Both figures
the sales guarantee is settled on therefore drifted upward as a gym lost
people — the exact opposite of what they are supposed to measure.

These assert the three things that has to mean: they leave the operational
lists, they leave the money and roster figures, and their history survives.
"""

import itertools
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.db import tenant_session
from app.models import Member, Subscription

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _gym(client: AsyncClient, slug: str) -> tuple[uuid.UUID, dict[str, str]]:
    username = f"life{next(_counter)}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": username,
            "manager_password": "hunter22", "manager_phone": f"+96177{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    return uuid.UUID(onboard.json()["gym_id"]), {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


async def _plan_id(client: AsyncClient, headers: dict[str, str]) -> str:
    plans = await client.get("/plans", headers=headers)
    return str(plans.json()[0]["id"])


def _payload(plan_id: str, phone: str) -> dict[str, object]:
    return {
        "name": "عضو", "name_en": "Member", "phone": phone, "plan_id": plan_id,
        "goal": "health", "level": "beginner", "height_cm": 175, "weight_kg": 80.0,
        "days_per_week": 3, "job": "desk", "sleep_hours": 7.0, "injuries": [],
    }


async def _add(client: AsyncClient, headers: dict[str, str], phone: str) -> str:
    created = await client.post(
        "/members", headers=_idem(headers), json=_payload(await _plan_id(client, headers), phone)
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def _lapse(gym_id: uuid.UUID, member_id: str, *, days_ago: int) -> None:
    async with tenant_session(gym_id) as session:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.member_id == uuid.UUID(member_id))
            )
        ).scalar_one()
        sold = sub.ends_at - sub.starts_at
        sub.ends_at = datetime.now(UTC) - timedelta(days=days_ago)
        sub.starts_at = sub.ends_at - sold


async def test_a_member_starts_active(client: AsyncClient) -> None:
    _, headers = await _gym(client, "life-a")
    member_id = await _add(client, headers, "+96174200001")
    got = await client.get(f"/members/{member_id}", headers=headers)
    assert got.json()["status"] == "active"
    assert got.json()["left_at"] is None


async def test_a_leaver_drops_off_the_roster_and_out_of_lapsed(client: AsyncClient) -> None:
    """The headline case. Someone who quit is not 'missing' — leaving them
    in is what made the lapsed list grow forever."""
    gym_id, headers = await _gym(client, "life-b")
    staying = await _add(client, headers, "+96174200002")
    leaving = await _add(client, headers, "+96174200003")
    # Both look lapsed: no attendance at all.
    await _lapse(gym_id, leaving, days_ago=40)

    before = await client.get("/members/lapsed?min_days=14", headers=headers)
    assert {m["id"] for m in before.json()} == {staying, leaving}

    gone = await client.post(
        f"/members/{leaving}/status", headers=_idem(headers), json={"status": "left"}
    )
    assert gone.status_code == 200, gone.text
    assert gone.json()["status"] == "left"
    assert gone.json()["left_at"] is not None

    after = await client.get("/members/lapsed?min_days=14", headers=headers)
    assert {m["id"] for m in after.json()} == {staying}

    roster = await client.get("/members", headers=headers)
    assert {m["id"] for m in roster.json()} == {staying}


async def test_a_leaver_stops_inflating_the_dashboard(client: AsyncClient) -> None:
    gym_id, headers = await _gym(client, "life-c")
    await _add(client, headers, "+96174200004")
    leaving = await _add(client, headers, "+96174200005")
    await _lapse(gym_id, leaving, days_ago=40)

    before = (await client.get("/analytics/summary?weeks=12", headers=headers)).json()
    assert before["active_members"] == 2
    assert before["left_members"] == 0

    await client.post(
        f"/members/{leaving}/status", headers=_idem(headers), json={"status": "left"}
    )

    after = (await client.get("/analytics/summary?weeks=12", headers=headers)).json()
    assert after["active_members"] == 1
    assert after["lapsed_now"] < before["lapsed_now"]
    # And the departure is now countable, which it never was before.
    assert after["left_members"] == 1


async def test_leaving_keeps_the_history(client: AsyncClient) -> None:
    """Not a delete. Their payments are what the collected figure is built
    from, and their photos are theirs (decision 11)."""
    gym_id, headers = await _gym(client, "life-d")
    member_id = await _add(client, headers, "+96174200006")
    await _lapse(gym_id, member_id, days_ago=5)
    await client.post(
        f"/members/{member_id}/payments",
        headers=_idem(headers),
        json={"amount_usd": 30.0, "method": "cash"},
    )
    await client.post(
        f"/members/{member_id}/status", headers=_idem(headers), json={"status": "left"}
    )

    # Still fetchable by id, and the payment still counts as collected.
    still_there = await client.get(f"/members/{member_id}", headers=headers)
    assert still_there.status_code == 200
    summary = (await client.get("/analytics/summary?weeks=12", headers=headers)).json()
    assert summary["collection"]["collected_usd"] == 30.0

    async with tenant_session(gym_id) as session:
        member = await session.get(Member, uuid.UUID(member_id))
        assert member is not None and member.status == "left"


async def test_marking_a_leaver_twice_does_not_move_the_date(client: AsyncClient) -> None:
    """A second tap on a slow connection must not rewrite when they left."""
    _, headers = await _gym(client, "life-e")
    member_id = await _add(client, headers, "+96174200007")
    first = await client.post(
        f"/members/{member_id}/status", headers=_idem(headers), json={"status": "left"}
    )
    again = await client.post(
        f"/members/{member_id}/status", headers=_idem(headers), json={"status": "left"}
    )
    assert again.json()["left_at"] == first.json()["left_at"]


async def test_a_member_can_come_back(client: AsyncClient) -> None:
    _, headers = await _gym(client, "life-f")
    member_id = await _add(client, headers, "+96174200008")
    await client.post(
        f"/members/{member_id}/status", headers=_idem(headers), json={"status": "left"}
    )
    back = await client.post(
        f"/members/{member_id}/status", headers=_idem(headers), json={"status": "active"}
    )
    assert back.json()["status"] == "active"
    # Cleared, so they are not counted as having left this quarter as well.
    assert back.json()["left_at"] is None
    roster = await client.get("/members", headers=headers)
    assert member_id in {m["id"] for m in roster.json()}


async def test_an_unknown_status_is_refused(client: AsyncClient) -> None:
    _, headers = await _gym(client, "life-g")
    member_id = await _add(client, headers, "+96174200009")
    bad = await client.post(
        f"/members/{member_id}/status", headers=_idem(headers), json={"status": "paused"}
    )
    assert bad.status_code == 422
    still = await client.get(f"/members/{member_id}", headers=headers)
    assert still.json()["status"] == "active"
