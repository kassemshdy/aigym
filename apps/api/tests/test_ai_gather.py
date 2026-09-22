import itertools
import uuid
from datetime import UTC, datetime

from httpx import AsyncClient

from app.ai import gather
from app.db import tenant_session
from app.models import Exercise, FoodEntry, Member, MemberProfile, Video, WorkoutSession, WorkoutSet

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


async def _new_gym(client: AsyncClient, *, slug: str) -> uuid.UUID:
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": f"mgr-{slug}",
            "manager_password": "hunter22", "manager_phone": f"+96179{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    return uuid.UUID(onboard.json()["gym_id"])


async def test_gather_member_context_returns_none_without_a_profile(client: AsyncClient) -> None:
    gym_id = await _new_gym(client, slug="gather-a")
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="No Profile",
                phone=f"+96170700{next(_counter):03d}", joined_at=datetime.now(UTC),
            )
        )

    async with tenant_session(gym_id) as session:
        result = await gather.gather_member_context(session, member_id)
    assert result is None


async def test_gather_member_context_maps_injuries_to_the_pydantic_shape(
    client: AsyncClient,
) -> None:
    gym_id = await _new_gym(client, slug="gather-b")
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Test Member",
                phone=f"+96170700{next(_counter):03d}", joined_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            MemberProfile(
                member_id=member_id, gym_id=gym_id, goal="strength", level="mid",
                height_cm=180, weight_kg=85.0, body_fat=15.0,
                injuries=[
                    {"body_part": "hip", "note": {"ar": "حوض", "en": "Hip"}, "severity": "mild"}
                ],
                days_per_week=5, job="active", sleep_hours=7.5, weight_trend=[],
            )
        )

    async with tenant_session(gym_id) as session:
        result = await gather.gather_member_context(session, member_id)

    assert result is not None
    assert result.weight_kg == 85.0
    assert result.injuries[0].body_part == "hip"
    assert result.injuries[0].severity == "mild"


async def test_gather_recent_sessions_resolves_exercise_names_in_the_requested_language(
    client: AsyncClient,
) -> None:
    gym_id = await _new_gym(client, slug="gather-c")
    member_id = uuid.uuid4()
    exercise_id = uuid.uuid4()
    session_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Test Member",
                phone=f"+96170700{next(_counter):03d}", joined_at=datetime.now(UTC),
            )
        )
        session.add(
            Exercise(
                id=exercise_id, gym_id=gym_id, name={"ar": "سكوات", "en": "Squat"},
                muscle_group="legs", active=True,
            )
        )
        await session.flush()
        session.add(
            WorkoutSession(
                id=session_id, gym_id=gym_id, member_id=member_id,
                started_at=datetime.now(UTC), finished_at=datetime.now(UTC), effort_band="hard",
            )
        )
        await session.flush()
        session.add(
            WorkoutSet(
                id=uuid.uuid4(), gym_id=gym_id, session_id=session_id, member_id=member_id,
                exercise_id=exercise_id, set_number=1, reps=10, weight_kg=60.0,
                at=datetime.now(UTC),
            )
        )

    async with tenant_session(gym_id) as session:
        rows_en = await gather.gather_recent_sessions(session, member_id, "en")
        rows_ar = await gather.gather_recent_sessions(session, member_id, "ar")

    assert rows_en[0].exercise_names == ["Squat"]
    assert rows_ar[0].exercise_names == ["سكوات"]
    assert rows_en[0].effort_band == "hard"


async def test_gather_today_food_excludes_yesterdays_entries(client: AsyncClient) -> None:
    gym_id = await _new_gym(client, slug="gather-d")
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Test Member",
                phone=f"+96170700{next(_counter):03d}", joined_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            FoodEntry(
                id=uuid.uuid4(), gym_id=gym_id, member_id=member_id, at=datetime.now(UTC),
                label="Today's lunch", kcal=500, protein=30, carbs=50, fat=10, source="manual",
            )
        )
        session.add(
            FoodEntry(
                id=uuid.uuid4(), gym_id=gym_id, member_id=member_id,
                at=datetime.now(UTC).replace(year=2020), label="Old entry", kcal=999,
                protein=1, carbs=1, fat=1, source="manual",
            )
        )

    async with tenant_session(gym_id) as session:
        rows = await gather.gather_today_food(session, member_id)

    assert [r.label for r in rows] == ["Today's lunch"]


async def test_gather_gym_catalog_only_returns_active_rows(client: AsyncClient) -> None:
    gym_id = await _new_gym(client, slug="gather-e")
    async with tenant_session(gym_id) as session:
        session.add(
            Exercise(
                id=uuid.uuid4(), gym_id=gym_id, name={"ar": "أ", "en": "Active Exercise"},
                muscle_group="legs", active=True,
            )
        )
        session.add(
            Exercise(
                id=uuid.uuid4(), gym_id=gym_id, name={"ar": "ب", "en": "Inactive Exercise"},
                muscle_group="legs", active=False,
            )
        )
        session.add(
            Video(
                id=uuid.uuid4(), gym_id=gym_id, title={"ar": "ج", "en": "Active Video"},
                provider="youtube", external_id="abc", muscle_group="legs", equipment="barbell",
                seconds=120, active=True,
            )
        )

    async with tenant_session(gym_id) as session:
        exercises, videos = await gather.gather_gym_catalog(session)

    exercise_names = {e.name["en"] for e in exercises}
    assert "Active Exercise" in exercise_names
    assert "Inactive Exercise" not in exercise_names
    assert videos[0].title["en"] == "Active Video"
