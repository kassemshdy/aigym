"""A plan's days repeat in order, and the next visit is the next day.

Decision 53. A plan used to be one flat list; a gym writes Push / Pull /
Legs. These pin the rotation (by sessions actually trained, not by the
calendar), that an abandoned session does not advance it, that a session
in progress keeps its day, and that an exercise cannot sit on a day the
plan does not have.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from app.domain.rotation import next_day
from tests.test_sessions import (
    _create_exercise,
    _create_member,
    _gym_and_staff_token,
    _idem,
)

PPL = [{"ar": "دفع", "en": "Push"}, {"ar": "سحب", "en": "Pull"}, {"ar": "أرجل", "en": "Legs"}]


def test_next_day_wraps_and_survives_a_shrunk_plan() -> None:
    assert next_day(3, None) == 0
    assert next_day(3, 0) == 1
    assert next_day(3, 2) == 0, "after the last day comes the first"
    assert next_day(1, 0) == 0
    assert next_day(2, 5) == 0, "a day the plan no longer has starts over"


async def _ppl_member(
    client: AsyncClient, slug: str, phone: str
) -> tuple[dict[str, str], str, list[str]]:
    _gym_id, headers = await _gym_and_staff_token(client, slug=slug)
    member_id = await _create_member(client, headers, phone=phone)
    ids = [await _create_exercise(client, headers, name_en=n) for n in ("Bench", "Row", "Squat")]
    body: dict[str, Any] = {
        "title": {"ar": "خطة", "en": "PPL"},
        "days": PPL,
        "exercises": [
            {"exercise_id": ids[i], "day_index": i, "sets": 3, "reps": {"ar": "10", "en": "10"}}
            for i in range(3)
        ],
    }
    created = await client.post(f"/members/{member_id}/programs", headers=_idem(headers), json=body)
    assert created.status_code == 201, created.text
    assert [e["day_index"] for e in created.json()["exercises"]] == [0, 1, 2]
    assert created.json()["days"] == PPL
    return headers, member_id, ids


async def _train(
    client: AsyncClient, headers: dict[str, str], member_id: str, program_id: str, day: int,
    exercise_id: str | None, *, minutes_ago: int,
) -> str:
    session_id = str(uuid.uuid4())
    started = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    created = await client.post(
        "/workout-sessions",
        headers=_idem(headers),
        json={
            "id": session_id, "member_id": member_id, "started_at": started.isoformat(),
            "program_id": program_id, "day_index": day,
        },
    )
    assert created.status_code == 201, created.text
    if exercise_id is not None:
        logged = await client.post(
            f"/workout-sessions/{session_id}/sets",
            headers=_idem(headers),
            json={
                "exercise_id": exercise_id, "set_number": 1, "reps": 10, "weight_kg": 40.0,
                "at": (started + timedelta(minutes=1)).isoformat(),
            },
        )
        assert logged.status_code == 201, logged.text
        finished = await client.patch(
            f"/workout-sessions/{session_id}",
            headers=_idem(headers),
            json={"finished_at": (started + timedelta(minutes=30)).isoformat()},
        )
        assert finished.status_code == 200, finished.text
    return session_id


async def test_the_next_visit_is_the_next_day(client: AsyncClient) -> None:
    headers, member_id, ids = await _ppl_member(client, "days-a", "+96174900001")
    today = (await client.get(f"/members/{member_id}/today-workout", headers=headers)).json()
    assert (today["day_index"], today["day_count"]) == (0, 3), "a new plan starts on day 1"
    assert [e["exercise_id"] for e in today["exercises"]] == [ids[0]], "only that day's exercises"
    program_id = today["program_id"]

    await _train(client, headers, member_id, program_id, 0, ids[0], minutes_ago=300)
    after_push = (await client.get(f"/members/{member_id}/today-workout", headers=headers)).json()
    assert after_push["day_index"] == 1
    assert [e["exercise_id"] for e in after_push["exercises"]] == [ids[1]]

    await _train(client, headers, member_id, program_id, 1, ids[1], minutes_ago=200)
    await _train(client, headers, member_id, program_id, 2, ids[2], minutes_ago=100)
    wrapped = (await client.get(f"/members/{member_id}/today-workout", headers=headers)).json()
    assert wrapped["day_index"] == 0, "after Legs comes Push again"

    chosen = (
        await client.get(f"/members/{member_id}/today-workout?day=2", headers=headers)
    ).json()
    assert chosen["day_index"] == 2, "a coach can pick a different day"


async def test_an_abandoned_session_does_not_advance_the_plan(client: AsyncClient) -> None:
    headers, member_id, ids = await _ppl_member(client, "days-b", "+96174900002")
    program_id = (
        await client.get(f"/members/{member_id}/today-workout", headers=headers)
    ).json()["program_id"]

    await _train(client, headers, member_id, program_id, 0, ids[0], minutes_ago=300)
    # Opened on Pull and walked away without logging a set.
    abandoned = await _train(client, headers, member_id, program_id, 1, None, minutes_ago=100)

    today = (await client.get(f"/members/{member_id}/today-workout", headers=headers)).json()
    # The open session is on Pull, so Pull it stays — not Legs.
    assert today["open_session_id"] == abandoned
    assert today["day_index"] == 1

    # Closed without a single set: it trained nothing, so Pull is still due.
    closed = await client.patch(
        f"/workout-sessions/{abandoned}",
        headers=_idem(headers),
        json={"finished_at": datetime.now(UTC).isoformat()},
    )
    assert closed.status_code == 200, closed.text
    after = (await client.get(f"/members/{member_id}/today-workout", headers=headers)).json()
    assert after["open_session_id"] is None
    assert after["day_index"] == 1, "an empty session advanced the plan"


async def test_an_exercise_cannot_sit_on_a_day_the_plan_lacks(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="days-c")
    member_id = await _create_member(client, headers, phone="+96174900003")
    exercise_id = await _create_exercise(client, headers, name_en="Bench")
    body = {
        "title": {"ar": "خطة", "en": "Plan"},
        "days": PPL[:2],
        "exercises": [
            {"exercise_id": exercise_id, "day_index": 2, "sets": 3, "reps": {"ar": "8", "en": "8"}}
        ],
    }
    refused = await client.post(f"/members/{member_id}/programs", headers=_idem(headers), json=body)
    assert refused.status_code == 422, refused.text


async def test_a_plan_from_before_days_is_a_one_day_plan(client: AsyncClient) -> None:
    """Every plan written before decision 53 has no days and every exercise
    on day 0 — the rotation must leave it exactly as it was."""
    _gym_id, headers = await _gym_and_staff_token(client, slug="days-d")
    member_id = await _create_member(client, headers, phone="+96174900004")
    exercise_id = await _create_exercise(client, headers, name_en="Bench")
    await client.post(
        f"/members/{member_id}/programs",
        headers=_idem(headers),
        json={
            "title": {"ar": "خطة", "en": "Plan"},
            "exercises": [{"exercise_id": exercise_id, "sets": 3, "reps": {"ar": "8", "en": "8"}}],
        },
    )
    today = (await client.get(f"/members/{member_id}/today-workout", headers=headers)).json()
    assert (today["day_index"], today["day_count"], today["days"]) == (0, 1, [])
    assert [e["exercise_id"] for e in today["exercises"]] == [exercise_id]


async def test_days_and_exercises_are_replaced_together(client: AsyncClient) -> None:
    headers, member_id, ids = await _ppl_member(client, "days-e", "+96174900005")
    program = (await client.get(f"/members/{member_id}/programs/active", headers=headers)).json()

    two_days = await client.patch(
        f"/programs/{program['id']}/exercises",
        headers=_idem(headers),
        json={
            "days": PPL[:2],
            "exercises": [
                {"exercise_id": ids[0], "day_index": 0, "sets": 4, "reps": {"ar": "8", "en": "8"}},
                {"exercise_id": ids[2], "day_index": 1, "sets": 4, "reps": {"ar": "8", "en": "8"}},
            ],
        },
    )
    assert two_days.status_code == 200, two_days.text
    assert two_days.json()["days"] == PPL[:2]
    assert [(e["exercise_id"], e["day_index"]) for e in two_days.json()["exercises"]] == [
        (ids[0], 0), (ids[2], 1),
    ]
