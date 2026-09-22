"""The impure half of context assembly — fetches rows via an already-open
CurrentSession and hands them to app/domain/ai_context.py's pure
composer. Lives in app/ai/, not app/domain/, precisely because it isn't
pure (per apps/api/AGENTS.md's domain/route split) — the equivalent of
what a route module does for its own domain function, just shared across
every AI-calling route (app/api/chat.py, stage 7).
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ai_context import (
    CatalogExerciseRow,
    CatalogVideoRow,
    FoodEntryRow,
    MemberContextRow,
    RecentSessionRow,
)
from app.models import Exercise, FoodEntry, MemberProfile, Video, WorkoutSession, WorkoutSet
from app.schemas.injuries import MemberInjury

RECENT_SESSION_LIMIT = 5


async def gather_member_context(
    session: AsyncSession, member_id: uuid.UUID
) -> MemberContextRow | None:
    profile = await session.get(MemberProfile, member_id)
    if profile is None:
        return None
    return MemberContextRow(
        goal=profile.goal,
        level=profile.level,
        height_cm=profile.height_cm,
        weight_kg=float(profile.weight_kg),
        body_fat=float(profile.body_fat) if profile.body_fat is not None else None,
        injuries=[MemberInjury(**i) for i in profile.injuries],
        days_per_week=profile.days_per_week,
        job=profile.job,
        sleep_hours=float(profile.sleep_hours),
        daily_kcal_target=profile.daily_kcal_target,
    )


async def gather_recent_sessions(
    session: AsyncSession, member_id: uuid.UUID, lang: str, limit: int = RECENT_SESSION_LIMIT
) -> list[RecentSessionRow]:
    result = await session.execute(
        select(WorkoutSession)
        .where(WorkoutSession.member_id == member_id)
        .order_by(WorkoutSession.started_at.desc())
        .limit(limit)
    )
    sessions = list(result.scalars().all())

    rows = []
    for s in sessions:
        names_result = await session.execute(
            select(Exercise.name)
            .join(WorkoutSet, WorkoutSet.exercise_id == Exercise.id)
            .where(WorkoutSet.session_id == s.id)
            .distinct()
        )
        names = [n.get(lang, n.get("en", "")) for n in names_result.scalars().all()]
        rows.append(
            RecentSessionRow(
                started_at=s.started_at, finished_at=s.finished_at,
                effort_band=s.effort_band, exercise_names=names,
            )
        )
    return rows


async def gather_today_food(session: AsyncSession, member_id: uuid.UUID) -> list[FoodEntryRow]:
    today = date.today()
    result = await session.execute(
        select(FoodEntry).where(
            FoodEntry.member_id == member_id,
            FoodEntry.at >= today,
            FoodEntry.at < today + timedelta(days=1),
        )
    )
    return [
        FoodEntryRow(label=f.label, kcal=f.kcal, protein=f.protein, carbs=f.carbs, fat=f.fat)
        for f in result.scalars().all()
    ]


async def gather_gym_catalog(
    session: AsyncSession,
) -> tuple[list[CatalogExerciseRow], list[CatalogVideoRow]]:
    exercises_result = await session.execute(select(Exercise).where(Exercise.active.is_(True)))
    exercises = [
        CatalogExerciseRow(name=e.name, muscle_group=e.muscle_group)
        for e in exercises_result.scalars().all()
    ]
    videos_result = await session.execute(select(Video).where(Video.active.is_(True)))
    videos = [
        CatalogVideoRow(title=v.title, muscle_group=v.muscle_group)
        for v in videos_result.scalars().all()
    ]
    return exercises, videos
