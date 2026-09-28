"""A member can be put on a coach's list. Decision 52.

Every coach used to see every member with nothing saying whose they were.
These pin who may assign (managers), whom (a coach at this gym, nobody
else), and that a coach who leaves takes nobody's assignment with them.
"""

import itertools
import uuid
from typing import Any

from httpx import AsyncClient

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _gym(client: AsyncClient, slug: str) -> dict[str, str]:
    username = f"owner-{slug}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Owner", "manager_username": username,
            "manager_password": "hunter22", "manager_phone": f"+96177{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _staff(
    client: AsyncClient, headers: dict[str, str], *, username: str, name: str, role: str
) -> str:
    created = await client.post(
        "/staff",
        headers=_idem(headers),
        json={
            "username": username, "password": "hunter22", "name": name,
            "phone": f"+96177{next(_counter):06d}", "role": role,
        },
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def _member(client: AsyncClient, headers: dict[str, str]) -> str:
    plan_id = (await client.get("/plans", headers=headers)).json()[0]["id"]
    payload: dict[str, Any] = {
        "name": "عضو", "name_en": "Member", "phone": f"+96177{next(_counter):06d}",
        "plan_id": plan_id, "goal": "health", "level": "new", "height_cm": 170,
        "weight_kg": 70.0, "injuries": [], "days_per_week": 3, "job": "desk",
        "sleep_hours": 7.0,
    }
    created = await client.post("/members", headers=_idem(headers), json=payload)
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def test_a_manager_puts_a_member_on_a_coachs_list(client: AsyncClient) -> None:
    headers = await _gym(client, "coach-assign-a")
    coach_id = await _staff(client, headers, username="coach-hadi", name="Hadi", role="coach")
    member_id = await _member(client, headers)

    assigned = await client.post(
        f"/members/{member_id}/coach", headers=_idem(headers), json={"coach_staff_id": coach_id}
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["coach_staff_id"] == coach_id
    assert assigned.json()["coach_name"] == "Hadi"

    listed = (await client.get("/members", headers=headers)).json()
    assert [(m["coach_staff_id"], m["coach_name"]) for m in listed] == [(coach_id, "Hadi")]

    cleared = await client.post(
        f"/members/{member_id}/coach", headers=_idem(headers), json={"coach_staff_id": None}
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["coach_staff_id"] is None
    assert cleared.json()["coach_name"] is None


async def test_only_a_coach_at_this_gym_can_be_assigned(client: AsyncClient) -> None:
    headers = await _gym(client, "coach-assign-b")
    manager_id = await _staff(client, headers, username="desk-lina", name="Lina", role="manager")
    member_id = await _member(client, headers)

    other_gym = await _gym(client, "coach-assign-b2")
    elsewhere = await _staff(client, other_gym, username="coach-away", name="Away", role="coach")

    for staff_id in (manager_id, elsewhere, str(uuid.uuid4())):
        refused = await client.post(
            f"/members/{member_id}/coach", headers=_idem(headers), json={"coach_staff_id": staff_id}
        )
        assert refused.status_code == 422, (staff_id, refused.text)


async def test_a_coach_cannot_assign_members(client: AsyncClient) -> None:
    headers = await _gym(client, "coach-assign-c")
    coach_id = await _staff(client, headers, username="coach-rima", name="Rima", role="coach")
    member_id = await _member(client, headers)
    login = await client.post(
        "/auth/staff/login", json={"username": "coach-rima", "password": "hunter22"}
    )
    coach_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    claimed = await client.post(
        f"/members/{member_id}/coach", headers=_idem(coach_headers),
        json={"coach_staff_id": coach_id},
    )
    assert claimed.status_code == 403, claimed.text


async def test_a_coach_who_stops_coaching_here_leaves_nobody_assigned_to_them(
    client: AsyncClient,
) -> None:
    headers = await _gym(client, "coach-assign-d")
    removed = await _staff(client, headers, username="coach-sam", name="Sam", role="coach")
    demoted = await _staff(client, headers, username="coach-tia", name="Tia", role="coach")
    kept = await _staff(client, headers, username="coach-zed", name="Zed", role="coach")
    members = [await _member(client, headers) for _ in range(3)]
    for member_id, coach_id in zip(members, (removed, demoted, kept), strict=True):
        await client.post(
            f"/members/{member_id}/coach", headers=_idem(headers),
            json={"coach_staff_id": coach_id},
        )

    await client.delete(f"/staff/{removed}", headers=_idem(headers))
    await client.patch(f"/staff/{demoted}", headers=_idem(headers), json={"role": "manager"})

    listed = (await client.get("/members", headers=headers)).json()
    by_id = {m["id"]: m["coach_staff_id"] for m in listed}
    assert by_id == {members[0]: None, members[1]: None, members[2]: kept}
