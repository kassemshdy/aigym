"""Plan CRUD. The delete guard is the one worth reading: subscriptions
reference plans with ON DELETE RESTRICT, so without an explicit check the
database refuses the delete as a 500 rather than something a gym owner can
act on.
"""

import itertools
import uuid

from httpx import AsyncClient

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _gym(client: AsyncClient, *, slug: str) -> dict[str, str]:
    username = f"owner-{slug}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Owner", "manager_username": username,
            "manager_password": "hunter22", "manager_phone": f"+96179{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _add_coach(client: AsyncClient, headers: dict[str, str]) -> dict[str, str]:
    username = f"coach{next(_counter)}"
    created = await client.post(
        "/staff",
        headers=_idem(headers),
        json={
            "username": username, "password": "hunter22", "name": "Coach",
            "phone": f"+96176{next(_counter):06d}", "role": "coach",
        },
    )
    assert created.status_code == 201, created.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_a_gym_replaces_the_starter_prices_it_was_given(client: AsyncClient) -> None:
    """The point of the stage: onboarding hands every gym $30/$80/$280, and
    those feed the dues arithmetic the guarantee is settled on."""
    headers = await _gym(client, slug="plans-a")

    created = await client.post(
        "/plans",
        headers=_idem(headers),
        json={"name": {"ar": "شهري", "en": "Monthly"}, "price_usd": 45.0, "days": 30},
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]
    assert created.json()["price_usd"] == 45.0

    raised = await client.patch(
        f"/plans/{plan_id}", headers=_idem(headers), json={"price_usd": 55.0}
    )
    assert raised.status_code == 200, raised.text
    assert raised.json()["price_usd"] == 55.0
    assert raised.json()["name"] == {"ar": "شهري", "en": "Monthly"}, "a price edit keeps the name"

    listing = (await client.get("/plans", headers=headers)).json()
    assert {p["id"]: p["price_usd"] for p in listing}[plan_id] == 55.0


async def test_a_plan_needs_a_name_in_both_languages(client: AsyncClient) -> None:
    """Saved with only English, the plan renders as a blank name on the
    Arabic side of the app rather than failing anywhere visible."""
    headers = await _gym(client, slug="plans-bilingual")

    for name in ({"en": "Monthly"}, {"ar": "شهري"}, {"ar": "", "en": "Monthly"}):
        refused = await client.post(
            "/plans",
            headers=_idem(headers),
            json={"name": name, "price_usd": 45.0, "days": 30},
        )
        assert refused.status_code == 422, f"{name} was accepted: {refused.text}"


async def test_a_plan_cannot_be_free_or_zero_days(client: AsyncClient) -> None:
    headers = await _gym(client, slug="plans-bounds")

    free = await client.post(
        "/plans",
        headers=_idem(headers),
        json={"name": {"ar": "مجاني", "en": "Free"}, "price_usd": 0, "days": 30},
    )
    assert free.status_code == 422

    forever = await client.post(
        "/plans",
        headers=_idem(headers),
        json={"name": {"ar": "أبدي", "en": "Forever"}, "price_usd": 10, "days": 0},
    )
    assert forever.status_code == 422


async def test_an_unused_plan_can_be_deleted(client: AsyncClient) -> None:
    headers = await _gym(client, slug="plans-delete")
    created = await client.post(
        "/plans",
        headers=_idem(headers),
        json={"name": {"ar": "تجريبي", "en": "Typo"}, "price_usd": 45.0, "days": 30},
    )
    plan_id = created.json()["id"]

    removed = await client.delete(f"/plans/{plan_id}", headers=_idem(headers))
    assert removed.status_code == 204, removed.text

    listing = (await client.get("/plans", headers=headers)).json()
    assert plan_id not in {p["id"] for p in listing}


async def test_deleting_a_plan_a_member_is_on_is_a_409_not_a_500(
    client: AsyncClient,
) -> None:
    """subscriptions.plan_id is ON DELETE RESTRICT. Without the explicit
    check the database raises at commit, outside the handler, and the gym
    owner sees a crash instead of a reason."""
    headers = await _gym(client, slug="plans-inuse")
    created = await client.post(
        "/plans",
        headers=_idem(headers),
        json={"name": {"ar": "شهري", "en": "Monthly"}, "price_usd": 45.0, "days": 30},
    )
    plan_id = created.json()["id"]

    member = await client.post(
        "/members",
        headers=_idem(headers),
        json={
            "name": "عضو", "name_en": "Member", "phone": f"+96170{next(_counter):06d}",
            "plan_id": plan_id, "goal": "health", "level": "new", "height_cm": 170,
            "weight_kg": 70, "days_per_week": 3, "job": "desk", "sleep_hours": 7,
        },
    )
    assert member.status_code == 201, member.text

    refused = await client.delete(f"/plans/{plan_id}", headers=_idem(headers))
    assert refused.status_code == 409, refused.text
    assert "1" in refused.json()["detail"], "says how many periods are affected"

    listing = (await client.get("/plans", headers=headers)).json()
    assert plan_id in {p["id"] for p in listing}, "a refused delete removes nothing"


async def test_a_coach_cannot_touch_the_price_list(client: AsyncClient) -> None:
    headers = await _gym(client, slug="plans-role")
    coach = await _add_coach(client, headers)
    existing = (await client.get("/plans", headers=headers)).json()[0]["id"]

    assert (
        await client.post(
            "/plans",
            headers=_idem(coach),
            json={"name": {"ar": "خطة", "en": "Plan"}, "price_usd": 10, "days": 30},
        )
    ).status_code == 403
    assert (
        await client.patch(f"/plans/{existing}", headers=_idem(coach), json={"price_usd": 1})
    ).status_code == 403
    assert (await client.delete(f"/plans/{existing}", headers=_idem(coach))).status_code == 403

    # A coach still reads the list — the member card shows a plan name.
    assert (await client.get("/plans", headers=coach)).status_code == 200


async def test_another_gyms_plan_is_a_404(client: AsyncClient) -> None:
    mine = await _gym(client, slug="plans-mine")
    theirs_headers = await _gym(client, slug="plans-theirs")
    theirs = (await client.get("/plans", headers=theirs_headers)).json()[0]["id"]

    assert (
        await client.patch(f"/plans/{theirs}", headers=_idem(mine), json={"price_usd": 1})
    ).status_code == 404
    assert (await client.delete(f"/plans/{theirs}", headers=_idem(mine))).status_code == 404

    # Untouched over there.
    still = (await client.get("/plans", headers=theirs_headers)).json()
    assert theirs in {p["id"] for p in still}
