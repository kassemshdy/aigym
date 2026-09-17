import itertools
import uuid
from typing import Any

from httpx import AsyncClient

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_phone_counter = itertools.count(1)


def _next_username() -> str:
    return f"manager{next(_phone_counter)}"


async def _gym_and_staff_token(
    client: AsyncClient, *, slug: str
) -> tuple[uuid.UUID, dict[str, str]]:
    manager_username = _next_username()
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
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _create_exercise(
    client: AsyncClient, headers: dict[str, str], *, name_en: str = "Squat"
) -> str:
    response = await client.post(
        "/exercises",
        headers=_idem(headers),
        json={"name": {"ar": name_en, "en": name_en}, "muscle_group": "legs"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _get_a_plan_id(client: AsyncClient, headers: dict[str, str]) -> str:
    plans = await client.get("/plans", headers=headers)
    return str(plans.json()[0]["id"])


def _member_payload(plan_id: str, phone: str) -> dict[str, Any]:
    return {
        "name": "عضو", "name_en": "Member", "phone": phone, "plan_id": plan_id,
        "goal": "health", "level": "new", "height_cm": 170, "weight_kg": 70.0,
        "body_fat": None, "injuries": [], "days_per_week": 3, "job": "desk", "sleep_hours": 7.0,
    }


async def _create_member(client: AsyncClient, headers: dict[str, str], *, phone: str) -> str:
    plan_id = await _get_a_plan_id(client, headers)
    response = await client.post(
        "/members", headers=_idem(headers), json=_member_payload(plan_id, phone)
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_create_and_list_exercises(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="exercises-a")
    exercise_id = await _create_exercise(client, headers, name_en="Bench Press")

    listed = await client.get("/exercises", headers=headers)
    assert listed.status_code == 200
    assert any(e["id"] == exercise_id for e in listed.json())


async def test_update_exercise(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="exercises-b")
    exercise_id = await _create_exercise(client, headers)

    updated = await client.patch(
        f"/exercises/{exercise_id}", headers=_idem(headers), json={"muscle_group": "back"}
    )
    assert updated.status_code == 200
    assert updated.json()["muscle_group"] == "back"


async def test_list_machines(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="machines-a")
    response = await client.get("/machines", headers=headers)
    assert response.status_code == 200
    assert response.json() == []  # onboarding seeds no machines — only scripts/seed.py does


async def test_member_has_no_active_program_by_default(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="programs-a")
    member_id = await _create_member(client, headers, phone="+96174100001")

    active = await client.get(f"/members/{member_id}/programs/active", headers=headers)
    assert active.status_code == 200
    assert active.json() is None


async def test_create_program_and_fetch_active(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="programs-b")
    member_id = await _create_member(client, headers, phone="+96174100002")
    exercise_id = await _create_exercise(client, headers, name_en="Squat")

    created = await client.post(
        f"/members/{member_id}/programs",
        headers=_idem(headers),
        json={
            "title": {"ar": "برنامج", "en": "Program"},
            "exercises": [
                {
                    "exercise_id": exercise_id, "sets": 4, "reps": {"ar": "٨", "en": "8"},
                    "target_weight_kg": 80.0,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert len(body["exercises"]) == 1
    assert body["exercises"][0]["exercise_name"]["en"] == "Squat"

    active = await client.get(f"/members/{member_id}/programs/active", headers=headers)
    assert active.status_code == 200
    assert active.json()["id"] == body["id"]


async def test_assigning_a_new_program_archives_the_old_one(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="programs-c")
    member_id = await _create_member(client, headers, phone="+96174100003")
    exercise_id = await _create_exercise(client, headers)

    first = await client.post(
        f"/members/{member_id}/programs",
        headers=_idem(headers),
        json={
            "title": {"ar": "أ", "en": "First"},
            "exercises": [
                {"exercise_id": exercise_id, "sets": 3, "reps": {"ar": "١٠", "en": "10"}}
            ],
        },
    )
    first_id = first.json()["id"]

    second = await client.post(
        f"/members/{member_id}/programs",
        headers=_idem(headers),
        json={
            "title": {"ar": "ب", "en": "Second"},
            "exercises": [{"exercise_id": exercise_id, "sets": 5, "reps": {"ar": "٥", "en": "5"}}],
        },
    )
    assert second.status_code == 201

    active = await client.get(f"/members/{member_id}/programs/active", headers=headers)
    assert active.json()["id"] == second.json()["id"]
    assert active.json()["id"] != first_id


async def test_replace_program_exercises(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="programs-d")
    member_id = await _create_member(client, headers, phone="+96174100004")
    exercise_a = await _create_exercise(client, headers, name_en="Squat")
    exercise_b = await _create_exercise(client, headers, name_en="Deadlift")

    created = await client.post(
        f"/members/{member_id}/programs",
        headers=_idem(headers),
        json={
            "title": {"ar": "أ", "en": "Program"},
            "exercises": [{"exercise_id": exercise_a, "sets": 3, "reps": {"ar": "١٠", "en": "10"}}],
        },
    )
    program_id = created.json()["id"]

    replaced = await client.patch(
        f"/programs/{program_id}/exercises",
        headers=_idem(headers),
        json={
            "exercises": [
                {"exercise_id": exercise_b, "sets": 4, "reps": {"ar": "٦", "en": "6"}},
            ]
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()["exercises"]) == 1
    assert replaced.json()["exercises"][0]["exercise_id"] == exercise_b


async def test_update_program_title_and_archive(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="programs-e")
    member_id = await _create_member(client, headers, phone="+96174100005")
    exercise_id = await _create_exercise(client, headers)

    created = await client.post(
        f"/members/{member_id}/programs",
        headers=_idem(headers),
        json={
            "title": {"ar": "أ", "en": "Program"},
            "exercises": [
                {"exercise_id": exercise_id, "sets": 3, "reps": {"ar": "١٠", "en": "10"}}
            ],
        },
    )
    program_id = created.json()["id"]

    archived = await client.patch(
        f"/programs/{program_id}", headers=_idem(headers), json={"archived": True}
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None

    active = await client.get(f"/members/{member_id}/programs/active", headers=headers)
    assert active.json() is None


async def test_create_program_404s_for_missing_member(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="programs-f")
    response = await client.post(
        f"/members/{uuid.uuid4()}/programs",
        headers=_idem(headers),
        json={"title": {"ar": "أ", "en": "Program"}, "exercises": []},
    )
    assert response.status_code == 404
