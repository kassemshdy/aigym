"""The cross-tenant isolation suite decision 7 calls for: tenant isolation
is 'the highest-stakes correctness property in the product,' so it gets its
own file and its own CI job (see .github/workflows/ci.yml's `tenancy` job)
rather than being one assertion among many in a general test run.

Two layers, both required:
  1. API layer — every endpoint must treat another gym's ids as if they
     don't exist (404, or absent from a list), never leak a 403 that
     confirms the id is real.
  2. Database layer — the policy itself, exercised directly through the
     app's own runtime role (never the owner/migrations role, which is a
     superuser and bypasses Row-Level Security regardless of what the
     policy says).
"""

import itertools
import uuid
from datetime import UTC, datetime
from typing import NamedTuple

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db import get_sessionmaker, tenant_session
from app.models import (
    Exercise,
    FoodEntry,
    Member,
    MemberProgram,
    NutritionLog,
    ProgramExercise,
    ProgressPhoto,
    Video,
    WorkoutSession,
    WorkoutSet,
)

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_phone_counter = itertools.count(1)


def _next_phone() -> str:
    return f"+96178{next(_phone_counter):06d}"


def _next_username() -> str:
    return f"manager{next(_phone_counter)}"


class NewGym(NamedTuple):
    gym_id: uuid.UUID
    headers: dict[str, str]
    manager_username: str


async def _new_gym(client: AsyncClient, *, slug: str) -> NewGym:
    manager_username = _next_username()
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": manager_username,
            "manager_password": "hunter22", "manager_phone": _next_phone(),
        },
    )
    assert onboard.status_code == 201, onboard.text
    gym_id = uuid.UUID(onboard.json()["gym_id"])

    login = await client.post(
        "/auth/staff/login", json={"username": manager_username, "password": "hunter22"}
    )
    token = login.json()["access_token"]
    return NewGym(gym_id, {"Authorization": f"Bearer {token}"}, manager_username)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _insert_member(gym_id: uuid.UUID, *, phone: str) -> uuid.UUID:
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Isolation Test Member",
                phone=phone, joined_at=datetime.now(UTC),
            )
        )
    return member_id


class TwoGyms(NamedTuple):
    a: NewGym
    b: NewGym
    member_a: uuid.UUID
    member_b: uuid.UUID


@pytest.fixture
async def two_gyms(client: AsyncClient) -> TwoGyms:
    """Gym A and gym B, each with one manager and one member."""
    gym_a = await _new_gym(client, slug="isolation-a")
    gym_b = await _new_gym(client, slug="isolation-b")
    member_a = await _insert_member(gym_a.gym_id, phone=_next_phone())
    member_b = await _insert_member(gym_b.gym_id, phone=_next_phone())
    return TwoGyms(gym_a, gym_b, member_a, member_b)


async def test_member_list_never_shows_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    list_a = await client.get("/members", headers=two_gyms.a.headers)
    list_b = await client.get("/members", headers=two_gyms.b.headers)
    ids_a = {m["id"] for m in list_a.json()}
    ids_b = {m["id"] for m in list_b.json()}

    assert str(two_gyms.member_a) in ids_a
    assert str(two_gyms.member_b) not in ids_a
    assert str(two_gyms.member_b) in ids_b
    assert str(two_gyms.member_a) not in ids_b


async def test_get_member_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    cross = await client.get(f"/members/{two_gyms.member_b}", headers=two_gyms.a.headers)
    assert cross.status_code == 404

    reverse = await client.get(f"/members/{two_gyms.member_a}", headers=two_gyms.b.headers)
    assert reverse.status_code == 404


async def test_patch_member_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.patch(
        f"/members/{two_gyms.member_b}",
        headers=_idem(two_gyms.a.headers),
        json={"name_en": "Hijacked"},
    )
    assert response.status_code == 404


async def test_record_payment_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.post(
        f"/members/{two_gyms.member_b}/payments",
        headers=_idem(two_gyms.a.headers),
        json={"amount_usd": 999.0, "method": "cash"},
    )
    assert response.status_code == 404


async def test_check_in_404s_for_the_other_gym(client: AsyncClient, two_gyms: TwoGyms) -> None:
    response = await client.post(
        "/check-ins",
        headers=_idem(two_gyms.a.headers),
        json={"member_id": str(two_gyms.member_b)},
    )
    assert response.status_code == 404


async def test_check_ins_today_never_shows_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    await client.post(
        "/check-ins", headers=_idem(two_gyms.a.headers), json={"member_id": str(two_gyms.member_a)}
    )
    await client.post(
        "/check-ins", headers=_idem(two_gyms.b.headers), json={"member_id": str(two_gyms.member_b)}
    )

    today_a = await client.get("/check-ins/today", headers=two_gyms.a.headers)
    member_ids_a = {c["member_id"] for c in today_a.json()}
    assert str(two_gyms.member_a) in member_ids_a
    assert str(two_gyms.member_b) not in member_ids_a


async def test_whatsapp_reminder_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.get(
        f"/members/{two_gyms.member_b}/whatsapp-reminder", headers=two_gyms.a.headers
    )
    assert response.status_code == 404


async def test_lapsed_list_never_shows_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    lapsed = await client.get("/members/lapsed?min_days=0", headers=two_gyms.a.headers)
    assert str(two_gyms.member_b) not in {m["id"] for m in lapsed.json()}


async def test_payments_list_never_shows_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    plan_a = (await client.get("/plans", headers=two_gyms.a.headers)).json()[0]["id"]
    plan_b = (await client.get("/plans", headers=two_gyms.b.headers)).json()[0]["id"]

    payment_a = await client.post(
        f"/members/{two_gyms.member_a}/payments",
        headers=_idem(two_gyms.a.headers),
        json={"amount_usd": 50.0, "method": "cash", "plan_id": plan_a},
    )
    payment_b = await client.post(
        f"/members/{two_gyms.member_b}/payments",
        headers=_idem(two_gyms.b.headers),
        json={"amount_usd": 50.0, "method": "cash", "plan_id": plan_b},
    )
    assert payment_a.status_code == 200, payment_a.text
    assert payment_b.status_code == 200, payment_b.text

    payments_a = await client.get("/payments", headers=two_gyms.a.headers)
    member_ids_a = {p["member_id"] for p in payments_a.json()}
    assert str(two_gyms.member_a) in member_ids_a
    assert str(two_gyms.member_b) not in member_ids_a


async def test_create_program_404s_for_the_other_gyms_member(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.post(
        f"/members/{two_gyms.member_b}/programs",
        headers=_idem(two_gyms.a.headers),
        json={"title": {"ar": "أ", "en": "Program"}, "exercises": []},
    )
    assert response.status_code == 404


async def test_get_active_program_404s_for_the_other_gyms_member(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.get(
        f"/members/{two_gyms.member_b}/programs/active", headers=two_gyms.a.headers
    )
    assert response.status_code == 404


async def test_replace_program_exercises_404s_for_the_other_gyms_program(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    exercise = await client.post(
        "/exercises",
        headers=_idem(two_gyms.b.headers),
        json={"name": {"ar": "سكوات", "en": "Squat"}, "muscle_group": "legs"},
    )
    program = await client.post(
        f"/members/{two_gyms.member_b}/programs",
        headers=_idem(two_gyms.b.headers),
        json={
            "title": {"ar": "أ", "en": "Program"},
            "exercises": [
                {"exercise_id": exercise.json()["id"], "sets": 3, "reps": {"ar": "١٠", "en": "10"}}
            ],
        },
    )
    program_id = program.json()["id"]

    cross = await client.patch(
        f"/programs/{program_id}/exercises",
        headers=_idem(two_gyms.a.headers),
        json={"exercises": []},
    )
    assert cross.status_code == 404


async def test_workout_session_404s_for_the_other_gyms_member(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.post(
        "/workout-sessions",
        headers=_idem(two_gyms.a.headers),
        json={"member_id": str(two_gyms.member_b), "started_at": datetime.now(UTC).isoformat()},
    )
    assert response.status_code == 404


async def test_get_workout_session_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    created = await client.post(
        "/workout-sessions",
        headers=_idem(two_gyms.b.headers),
        json={"member_id": str(two_gyms.member_b), "started_at": datetime.now(UTC).isoformat()},
    )
    session_id = created.json()["id"]

    cross = await client.get(f"/workout-sessions/{session_id}", headers=two_gyms.a.headers)
    assert cross.status_code == 404


async def test_today_workout_404s_for_the_other_gyms_member(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.get(
        f"/members/{two_gyms.member_b}/today-workout", headers=two_gyms.a.headers
    )
    assert response.status_code == 404


async def test_list_workout_sessions_404s_for_the_other_gyms_member(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.get(
        f"/members/{two_gyms.member_b}/workout-sessions", headers=two_gyms.a.headers
    )
    assert response.status_code == 404


async def test_nutrition_log_404s_for_the_other_gyms_member(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    response = await client.post(
        f"/members/{two_gyms.member_b}/nutrition-logs",
        headers=_idem(two_gyms.a.headers),
        json={
            "at": datetime.now(UTC).isoformat(), "band": "moderate", "meals": [],
            "source": "member",
        },
    )
    assert response.status_code == 404


async def test_update_check_in_404s_for_the_other_gym(
    client: AsyncClient, two_gyms: TwoGyms
) -> None:
    created = await client.post(
        "/check-ins", headers=_idem(two_gyms.b.headers), json={"member_id": str(two_gyms.member_b)}
    )
    check_in_id = created.json()["id"]

    cross = await client.patch(
        f"/check-ins/{check_in_id}", headers=_idem(two_gyms.a.headers), json={"status": "training"}
    )
    assert cross.status_code == 404


async def test_staff_list_never_shows_the_other_gym(client: AsyncClient, two_gyms: TwoGyms) -> None:
    listed_a = await client.get("/staff", headers=two_gyms.a.headers)
    usernames_a = {row["username"] for row in listed_a.json()}
    assert two_gyms.a.manager_username in usernames_a
    assert two_gyms.b.manager_username not in usernames_a


async def test_exercises_never_show_the_other_gym(client: AsyncClient, two_gyms: TwoGyms) -> None:
    exercise_a = await client.post(
        "/exercises",
        headers=_idem(two_gyms.a.headers),
        json={"name": {"ar": "سكوات", "en": "Squat A"}, "muscle_group": "legs"},
    )
    exercise_b = await client.post(
        "/exercises",
        headers=_idem(two_gyms.b.headers),
        json={"name": {"ar": "سكوات", "en": "Squat B"}, "muscle_group": "legs"},
    )
    assert exercise_a.status_code == 201
    assert exercise_b.status_code == 201

    exercises_a = await client.get("/exercises", headers=two_gyms.a.headers)
    listed_a = {e["id"] for e in exercises_a.json()}
    assert exercise_a.json()["id"] in listed_a
    assert exercise_b.json()["id"] not in listed_a


async def test_plans_never_shows_the_other_gym(client: AsyncClient, two_gyms: TwoGyms) -> None:
    plans_a = {p["id"] for p in (await client.get("/plans", headers=two_gyms.a.headers)).json()}
    plans_b = {p["id"] for p in (await client.get("/plans", headers=two_gyms.b.headers)).json()}
    # Each gym's onboarding seeds its own starter plans; the sets must be disjoint.
    assert plans_a.isdisjoint(plans_b)


async def test_staff_login_never_crosses_gyms(client: AsyncClient) -> None:
    """A staff account belongs to the gym it was onboarded into. Logging in
    must never resolve to a different gym's id, even by coincidence of
    query ordering."""
    gym_a = await _new_gym(client, slug="isolation-login-a")
    gym_b = await _new_gym(client, slug="isolation-login-b")

    login_a = await client.post(
        "/auth/staff/login", json={"username": gym_a.manager_username, "password": "hunter22"}
    )
    login_b = await client.post(
        "/auth/staff/login", json={"username": gym_b.manager_username, "password": "hunter22"}
    )

    me_a = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login_a.json()['access_token']}"}
    )
    me_b = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login_b.json()['access_token']}"}
    )
    assert me_a.json()["gym_id"] == str(gym_a.gym_id)
    assert me_b.json()["gym_id"] == str(gym_b.gym_id)
    assert login_a.json()["access_token"] != login_b.json()["access_token"]


# --------------------------------------------------------------------------
# Database layer: exercised directly through the app's own runtime role
# (aigym_app, NOT the owner/migrations role — a superuser bypasses RLS
# regardless of policy, so testing through it would prove nothing).
# --------------------------------------------------------------------------


async def test_rls_blocks_cross_gym_select_at_the_database_layer(two_gyms: TwoGyms) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.gym_id', :gym_id, true)"),
            {"gym_id": str(two_gyms.a.gym_id)},
        )
        result = await session.execute(select(Member).where(Member.id == two_gyms.member_b))
        assert result.scalar_one_or_none() is None, (
            "gym A's connection could read gym B's member row directly — RLS is not enforcing"
        )


async def test_rls_blocks_query_with_no_gym_id_set_at_all(two_gyms: TwoGyms) -> None:
    """A connection that never calls set_config must fail closed — zero
    rows, not every gym's rows and not an error."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        result = await session.execute(select(Member))
        assert result.scalars().all() == []


async def test_rls_blocks_cross_gym_write_at_the_database_layer(two_gyms: TwoGyms) -> None:
    """WITH CHECK, not just USING: gym A's connection must not be able to
    insert a row claiming gym B's id, even though it knows gym B's id."""
    sessionmaker = get_sessionmaker()
    with pytest.raises(Exception, match="row-level security"):
        async with sessionmaker() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.gym_id', :gym_id, true)"),
                {"gym_id": str(two_gyms.a.gym_id)},
            )
            session.add(
                Member(
                    id=uuid.uuid4(), gym_id=two_gyms.b.gym_id, name="x", name_en="x",
                    phone=_next_phone(), joined_at=datetime.now(UTC),
                )
            )
            await session.flush()


# --------------------------------------------------------------------------
# Phase 3 floor tables. API-layer coverage for exercises/programs lands
# alongside their endpoints (stage 2); sessions/sets/nutrition alongside
# theirs (stage 3). This is the database layer only, exercised the same way
# as the tests above — proving the policy blocks a cross-gym SELECT for
# every one of the six new gym-scoped tables, not just Member.
# --------------------------------------------------------------------------


async def _select_as_gym(model: type, row_id: uuid.UUID, gym_id: uuid.UUID) -> object | None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.gym_id', :gym_id, true)"), {"gym_id": str(gym_id)}
        )
        result = await session.execute(select(model).where(model.id == row_id))
        return result.scalar_one_or_none()


async def test_rls_blocks_cross_gym_select_on_every_floor_table(two_gyms: TwoGyms) -> None:
    exercise_id = uuid.uuid4()
    program_id = uuid.uuid4()
    program_exercise_id = uuid.uuid4()
    session_id = uuid.uuid4()
    set_id = uuid.uuid4()
    nutrition_id = uuid.uuid4()

    async with tenant_session(two_gyms.b.gym_id) as session:
        session.add(
            Exercise(
                id=exercise_id, gym_id=two_gyms.b.gym_id,
                name={"ar": "سكوات", "en": "Squat"}, muscle_group="legs", active=True,
            )
        )
        await session.flush()
        session.add(
            MemberProgram(
                id=program_id, gym_id=two_gyms.b.gym_id, member_id=two_gyms.member_b,
                title={"ar": "برنامج", "en": "Program"},
            )
        )
        await session.flush()
        session.add(
            ProgramExercise(
                id=program_exercise_id, gym_id=two_gyms.b.gym_id, program_id=program_id,
                exercise_id=exercise_id, order_index=0, sets=3, reps={"ar": "١٠", "en": "10"},
            )
        )
        session.add(
            WorkoutSession(
                id=session_id, gym_id=two_gyms.b.gym_id, member_id=two_gyms.member_b,
                started_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            WorkoutSet(
                id=set_id, gym_id=two_gyms.b.gym_id, session_id=session_id,
                member_id=two_gyms.member_b, exercise_id=exercise_id, set_number=1,
                reps=10, weight_kg=60.0, at=datetime.now(UTC),
            )
        )
        session.add(
            NutritionLog(
                id=nutrition_id, gym_id=two_gyms.b.gym_id, member_id=two_gyms.member_b,
                at=datetime.now(UTC), band="moderate", meals=[], source="member",
            )
        )

    for model, row_id in [
        (Exercise, exercise_id),
        (MemberProgram, program_id),
        (ProgramExercise, program_exercise_id),
        (WorkoutSession, session_id),
        (WorkoutSet, set_id),
        (NutritionLog, nutrition_id),
    ]:
        assert await _select_as_gym(model, row_id, two_gyms.a.gym_id) is None, (
            f"gym A could read gym B's {model.__tablename__} row — RLS is not enforcing"
        )
        assert await _select_as_gym(model, row_id, two_gyms.b.gym_id) is not None, (
            f"gym B could not read its own {model.__tablename__} row — fixture or policy is broken"
        )


# --------------------------------------------------------------------------
# Phase 4 content tables (videos, food_entries, progress_photos). API-layer
# coverage lands alongside each table's endpoints (stages 3-5) — this is the
# database layer only, same shape as the floor-table test above.
# --------------------------------------------------------------------------


async def test_rls_blocks_cross_gym_select_on_every_content_table(two_gyms: TwoGyms) -> None:
    video_id = uuid.uuid4()
    food_entry_id = uuid.uuid4()
    progress_photo_id = uuid.uuid4()

    async with tenant_session(two_gyms.b.gym_id) as session:
        session.add(
            Video(
                id=video_id, gym_id=two_gyms.b.gym_id,
                title={"ar": "سكوات", "en": "Squat"}, provider="youtube",
                external_id="abc123", muscle_group="legs", equipment="barbell",
                seconds=120, active=True,
            )
        )
        session.add(
            FoodEntry(
                id=food_entry_id, gym_id=two_gyms.b.gym_id, member_id=two_gyms.member_b,
                at=datetime.now(UTC), label="Eggs", kcal=300, protein=20, carbs=10,
                fat=15, source="manual",
            )
        )
        session.add(
            ProgressPhoto(
                id=progress_photo_id, gym_id=two_gyms.b.gym_id, member_id=two_gyms.member_b,
                at=datetime.now(UTC), photo_key="fake-key.jpg",
            )
        )

    for model, row_id in [
        (Video, video_id),
        (FoodEntry, food_entry_id),
        (ProgressPhoto, progress_photo_id),
    ]:
        assert await _select_as_gym(model, row_id, two_gyms.a.gym_id) is None, (
            f"gym A could read gym B's {model.__tablename__} row — RLS is not enforcing"
        )
        assert await _select_as_gym(model, row_id, two_gyms.b.gym_id) is not None, (
            f"gym B could not read its own {model.__tablename__} row — fixture or policy is broken"
        )
