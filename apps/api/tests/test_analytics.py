"""GET /analytics/summary.

The expected values here are worked out by hand from a fixture with known
dates and prices. This is the number a gym owner is shown to settle a
money-back guarantee, so "the endpoint returned something" is not evidence
that it is right.
"""

import itertools
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.db import tenant_session
from app.models import Member, Plan, Subscription

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)

WEEKS = 12
WINDOW_DAYS = WEEKS * 7  # 84


async def _gym_and_staff_token(
    client: AsyncClient, *, slug: str
) -> tuple[uuid.UUID, dict[str, str]]:
    username = f"mgr-{slug}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": username,
            "manager_password": "hunter22", "manager_phone": f"+96179{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    gym_id = uuid.UUID(onboard.json()["gym_id"])
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    assert login.status_code == 200, login.text
    return gym_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _seed_scenario(gym_id: uuid.UUID) -> None:
    """Four members, every date relative to now so this never depends on
    the calendar:

      A — $30 period ended 30d ago, renewed 2 days later   -> on time
      B — $80 period ended 40d ago, renewed 20 days later  -> late, collected
      C — $280 period ended 50d ago, never renewed         -> uncollected
      D — $30 period still running, joined 5d ago          -> nothing due

    A, B and C joined 100 days ago, which is before the 84-day window and
    inside the one before it.
    """
    now = datetime.now(UTC)
    async with tenant_session(gym_id) as session:
        prices = {}
        for amount in (30.0, 80.0, 280.0):
            plan = Plan(
                id=uuid.uuid4(), gym_id=gym_id,
                name={"ar": f"خطة {amount:g}", "en": f"Plan {amount:g}"},
                price_usd=amount, days=30,
            )
            session.add(plan)
            prices[amount] = plan.id
        await session.flush()

        def add_member(tag: str, joined_days_ago: int) -> uuid.UUID:
            member_id = uuid.uuid4()
            session.add(
                Member(
                    id=member_id, gym_id=gym_id, name=f"عضو {tag}", name_en=f"Member {tag}",
                    phone=f"+9617050{next(_counter):04d}",
                    joined_at=now - timedelta(days=joined_days_ago),
                )
            )
            return member_id

        def add_period(
            member_id: uuid.UUID, price: float, *, ends_days_ago: int
        ) -> None:
            ends = now - timedelta(days=ends_days_ago)
            session.add(
                Subscription(
                    id=uuid.uuid4(), gym_id=gym_id, member_id=member_id,
                    # The price rides on the period, not the plan — which is
                    # the point of decision 42 and why `prices[price]` is now
                    # only here to satisfy the foreign key.
                    plan_id=prices[price], price_usd=price, days=30,
                    starts_at=ends - timedelta(days=30), ends_at=ends,
                )
            )

        def add_renewal(
            member_id: uuid.UUID, price: float, *, starts_days_ago: int
        ) -> None:
            starts = now - timedelta(days=starts_days_ago)
            session.add(
                Subscription(
                    id=uuid.uuid4(), gym_id=gym_id, member_id=member_id,
                    plan_id=prices[price], price_usd=price, days=30,
                    starts_at=starts,
                    ends_at=starts + timedelta(days=30),
                )
            )

        a = add_member("A", 100)
        b = add_member("B", 100)
        c = add_member("C", 100)
        d = add_member("D", 5)
        # No relationship() is declared on these models (plain FK columns),
        # so the unit of work cannot order members before their
        # subscriptions by itself — same note seed.py carries.
        await session.flush()

        add_period(a, 30.0, ends_days_ago=30)
        add_renewal(a, 30.0, starts_days_ago=28)  # 2 days late -> on time

        add_period(b, 80.0, ends_days_ago=40)
        add_renewal(b, 80.0, starts_days_ago=20)  # 20 days late -> collected

        add_period(c, 280.0, ends_days_ago=50)  # never renewed

        add_renewal(d, 30.0, starts_days_ago=5)  # still running


async def test_collection_figures_match_the_hand_computed_scenario(
    client: AsyncClient,
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="analytics-a")
    await _seed_scenario(gym_id)

    response = await client.get(f"/analytics/summary?weeks={WEEKS}", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    collection = body["collection"]
    assert collection["due_count"] == 3, "A, B and C fell due; D's period is still running"
    assert collection["on_time_count"] == 1, "only A renewed inside 7 days"
    assert collection["on_time_rate"] == round(1 / 3, 4)
    assert collection["collected_usd"] == 110.0, "A's $30 plus B's $80; late still counts"
    assert collection["uncollected_usd"] == 280.0, "C never renewed"


async def test_new_member_counts_split_across_the_two_windows(
    client: AsyncClient,
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="analytics-b")
    await _seed_scenario(gym_id)

    body = (
        await client.get(f"/analytics/summary?weeks={WEEKS}", headers=headers)
    ).json()
    # D joined 5 days ago; A, B and C joined 100 days ago, which is outside
    # the 84-day window and inside the 84 before that.
    assert body["new_members"] == 1
    assert body["new_members_previous"] == 3
    assert body["active_members"] == 4


async def test_lapsed_counts_members_with_no_attendance_at_all(
    client: AsyncClient,
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="analytics-c")
    await _seed_scenario(gym_id)

    body = (
        await client.get(f"/analytics/summary?weeks={WEEKS}", headers=headers)
    ).json()
    assert body["lapsed_now"] == 4, "nobody has ever checked in"
    # Only A, B and C existed when the window opened — counting D against a
    # date before they joined would invent churn.
    assert body["lapsed_at_window_start"] == 3


async def test_the_weekly_series_has_one_point_per_week_oldest_first(
    client: AsyncClient,
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="analytics-d")
    await _seed_scenario(gym_id)

    body = (
        await client.get(f"/analytics/summary?weeks={WEEKS}", headers=headers)
    ).json()
    series = body["series"]
    assert len(series) == WEEKS
    starts = [p["week_start"] for p in series]
    assert starts == sorted(starts), "the series must read oldest first"
    # The three due periods land in the window, so the series accounts for
    # exactly what the headline figure counted.
    assert sum(p["collected_usd"] for p in series) == 110.0


async def test_an_empty_gym_reports_no_rate_rather_than_zero_percent(
    client: AsyncClient,
) -> None:
    """0% means every renewal was missed. A gym with nothing due has to be
    distinguishable from that."""
    _gym_id, headers = await _gym_and_staff_token(client, slug="analytics-empty")

    body = (
        await client.get(f"/analytics/summary?weeks={WEEKS}", headers=headers)
    ).json()
    assert body["collection"]["due_count"] == 0
    assert body["collection"]["on_time_rate"] is None


async def test_a_coach_cannot_read_the_owner_dashboard(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="analytics-role")
    coach = await client.post(
        "/staff",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "name": "Coach", "phone": f"+96176{next(_counter):06d}",
            "username": f"coach{next(_counter)}", "password": "hunter22", "role": "coach",
        },
    )
    assert coach.status_code == 201, coach.text
    login = await client.post(
        "/auth/staff/login",
        json={"username": coach.json()["username"], "password": "hunter22"},
    )
    coach_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    forbidden = await client.get("/analytics/summary", headers=coach_headers)
    assert forbidden.status_code == 403


async def test_one_gyms_numbers_never_include_anothers(client: AsyncClient) -> None:
    gym_a, headers_a = await _gym_and_staff_token(client, slug="analytics-iso-a")
    _gym_b, headers_b = await _gym_and_staff_token(client, slug="analytics-iso-b")
    await _seed_scenario(gym_a)

    a_body = (await client.get(f"/analytics/summary?weeks={WEEKS}", headers=headers_a)).json()
    b_body = (await client.get(f"/analytics/summary?weeks={WEEKS}", headers=headers_b)).json()

    assert a_body["collection"]["due_count"] == 3
    assert a_body["active_members"] == 4
    assert b_body["collection"]["due_count"] == 0
    assert b_body["collection"]["uncollected_usd"] == 0.0
    assert b_body["active_members"] == 0
