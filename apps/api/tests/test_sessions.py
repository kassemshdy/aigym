import itertools
import uuid
from datetime import UTC, datetime, timedelta
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


async def _create_exercise(client: AsyncClient, headers: dict[str, str], *, name_en: str) -> str:
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


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def test_create_workout_session_with_client_id_and_log_a_set(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="sessions-a")
    member_id = await _create_member(client, headers, phone="+96174200001")
    exercise_id = await _create_exercise(client, headers, name_en="Squat")

    session_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    created = await client.post(
        "/workout-sessions",
        headers=_idem(headers),
        json={
            "id": session_id, "member_id": member_id, "started_at": _iso(started_at),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["id"] == session_id

    logged_at = started_at + timedelta(minutes=2)
    set_response = await client.post(
        f"/workout-sessions/{session_id}/sets",
        headers=_idem(headers),
        json={
            "exercise_id": exercise_id, "set_number": 1, "reps": 8, "weight_kg": 80.0,
            "at": _iso(logged_at),
        },
    )
    assert set_response.status_code == 201, set_response.text
    assert set_response.json()["weight_kg"] == 80.0

    fetched = await client.get(f"/workout-sessions/{session_id}", headers=headers)
    assert fetched.status_code == 200
    assert len(fetched.json()["sets"]) == 1


async def test_finish_workout_session(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="sessions-b")
    member_id = await _create_member(client, headers, phone="+96174200002")

    started_at = datetime.now(UTC)
    created = await client.post(
        "/workout-sessions",
        headers=_idem(headers),
        json={"member_id": member_id, "started_at": _iso(started_at)},
    )
    session_id = created.json()["id"]

    finished_at = started_at + timedelta(minutes=45)
    finished = await client.patch(
        f"/workout-sessions/{session_id}",
        headers=_idem(headers),
        json={"finished_at": _iso(finished_at), "effort_band": "hard"},
    )
    assert finished.status_code == 200
    assert finished.json()["effort_band"] == "hard"
    assert finished.json()["finished_at"] is not None


async def test_create_workout_session_404s_for_missing_member(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="sessions-c")
    response = await client.post(
        "/workout-sessions",
        headers=_idem(headers),
        json={"member_id": str(uuid.uuid4()), "started_at": _iso(datetime.now(UTC))},
    )
    assert response.status_code == 404


async def test_log_set_404s_for_missing_exercise(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="sessions-d")
    member_id = await _create_member(client, headers, phone="+96174200004")
    created = await client.post(
        "/workout-sessions",
        headers=_idem(headers),
        json={"member_id": member_id, "started_at": _iso(datetime.now(UTC))},
    )
    session_id = created.json()["id"]

    response = await client.post(
        f"/workout-sessions/{session_id}/sets",
        headers=_idem(headers),
        json={
            "exercise_id": str(uuid.uuid4()), "set_number": 1, "reps": 8, "weight_kg": 50.0,
            "at": _iso(datetime.now(UTC)),
        },
    )
    assert response.status_code == 404


async def test_today_workout_merges_program_with_last_weight(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="sessions-e")
    member_id = await _create_member(client, headers, phone="+96174200005")
    exercise_id = await _create_exercise(client, headers, name_en="Bench Press")

    await client.post(
        f"/members/{member_id}/programs",
        headers=_idem(headers),
        json={
            "title": {"ar": "أ", "en": "Program"},
            "exercises": [
                {
                    "exercise_id": exercise_id, "sets": 4, "reps": {"ar": "٨", "en": "8"},
                    "target_weight_kg": 60.0,
                }
            ],
        },
    )

    before = await client.get(f"/members/{member_id}/today-workout", headers=headers)
    assert before.status_code == 200
    assert before.json()["exercises"][0]["last_weight_kg"] is None
    assert before.json()["open_session_id"] is None

    session_created = await client.post(
        "/workout-sessions",
        headers=_idem(headers),
        json={"member_id": member_id, "started_at": _iso(datetime.now(UTC))},
    )
    session_id = session_created.json()["id"]
    await client.post(
        f"/workout-sessions/{session_id}/sets",
        headers=_idem(headers),
        json={
            "exercise_id": exercise_id, "set_number": 1, "reps": 8, "weight_kg": 65.0,
            "at": _iso(datetime.now(UTC)),
        },
    )

    after = await client.get(f"/members/{member_id}/today-workout", headers=headers)
    assert after.json()["exercises"][0]["last_weight_kg"] == 65.0
    assert after.json()["open_session_id"] == session_id

    await client.patch(
        f"/workout-sessions/{session_id}",
        headers=_idem(headers),
        json={"finished_at": _iso(datetime.now(UTC))},
    )
    finished_state = await client.get(f"/members/{member_id}/today-workout", headers=headers)
    assert finished_state.json()["open_session_id"] is None


async def test_today_workout_with_no_active_program(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="sessions-f")
    member_id = await _create_member(client, headers, phone="+96174200006")

    response = await client.get(f"/members/{member_id}/today-workout", headers=headers)
    assert response.status_code == 200
    assert response.json()["program_id"] is None
    assert response.json()["exercises"] == []


async def test_list_workout_sessions_returns_finished_only_most_recent_first(
    client: AsyncClient,
) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="sessions-g")
    member_id = await _create_member(client, headers, phone="+96174200009")
    exercise_id = await _create_exercise(client, headers, name_en="Deadlift")

    now = datetime.now(UTC)

    async def _finished_session(started_at: datetime, reps: int, weight_kg: float) -> str:
        created = await client.post(
            "/workout-sessions",
            headers=_idem(headers),
            json={"member_id": member_id, "started_at": _iso(started_at)},
        )
        session_id = created.json()["id"]
        await client.post(
            f"/workout-sessions/{session_id}/sets",
            headers=_idem(headers),
            json={
                "exercise_id": exercise_id, "set_number": 1, "reps": reps, "weight_kg": weight_kg,
                "at": _iso(started_at),
            },
        )
        await client.patch(
            f"/workout-sessions/{session_id}",
            headers=_idem(headers),
            json={"finished_at": _iso(started_at + timedelta(minutes=40))},
        )
        return str(session_id)

    older_id = await _finished_session(now - timedelta(days=3), reps=8, weight_kg=60.0)
    newer_id = await _finished_session(now - timedelta(days=1), reps=5, weight_kg=100.0)

    # An open (unfinished) session must not appear in the history list.
    await client.post(
        "/workout-sessions",
        headers=_idem(headers),
        json={"member_id": member_id, "started_at": _iso(now)},
    )

    listed = await client.get(f"/members/{member_id}/workout-sessions", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert [s["id"] for s in body] == [newer_id, older_id]
    assert all(s["finished_at"] is not None for s in body)
    assert body[0]["sets"][0]["weight_kg"] == 100.0


async def test_list_workout_sessions_404s_for_missing_member(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="sessions-h")
    response = await client.get(f"/members/{uuid.uuid4()}/workout-sessions", headers=headers)
    assert response.status_code == 404


async def test_create_and_list_nutrition_logs(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="nutrition-a")
    member_id = await _create_member(client, headers, phone="+96174200007")

    created = await client.post(
        f"/members/{member_id}/nutrition-logs",
        headers=_idem(headers),
        json={
            "at": _iso(datetime.now(UTC)), "band": "moderate",
            "meals": [{"ar": "دجاج ورز", "en": "Chicken and rice"}], "source": "member",
        },
    )
    assert created.status_code == 201, created.text

    listed = await client.get(f"/members/{member_id}/nutrition-logs", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["band"] == "moderate"


async def test_update_check_in_status(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="checkins-status-a")
    member_id = await _create_member(client, headers, phone="+96174200008")

    created = await client.post(
        "/check-ins", headers=_idem(headers), json={"member_id": member_id}
    )
    check_in_id = created.json()["id"]

    updated = await client.patch(
        f"/check-ins/{check_in_id}", headers=_idem(headers), json={"status": "training"}
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "training"


async def test_update_check_in_404s_for_missing_check_in(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="checkins-status-b")
    response = await client.patch(
        f"/check-ins/{uuid.uuid4()}", headers=_idem(headers), json={"status": "training"}
    )
    assert response.status_code == 404
