"""Workout sessions and sets, plus 'today's workout' resolution.

Session and set ids are exceptionally client-mintable (see docs/DECISIONS.md):
a session started offline must be referenceable by the very next queued 'log
a set' request before any server round trip has happened. Every write here
requires the client to send its own `started_at`/`at`/`finished_at` — the
client, not server now(), is the source of truth for when something actually
happened, since a queued write can replay minutes or hours after it was made.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.programs import _active_program
from app.deps import CurrentClaims, CurrentSession, require_role
from app.domain.rotation import next_day
from app.domain.workout import ProgramExerciseRow, resolve_today_workout
from app.models import (
    CheckIn,
    Exercise,
    Machine,
    Member,
    MemberProgram,
    ProgramExercise,
    WorkoutSession,
    WorkoutSet,
)
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["sessions"])

ManagerOrCoach = Depends(require_role("super_admin", "manager", "coach"))


class WorkoutSetOut(BaseModel):
    id: uuid.UUID
    exercise_id: uuid.UUID
    set_number: int
    reps: int
    weight_kg: float
    machine_id: uuid.UUID | None
    at: datetime

    model_config = {"from_attributes": True}


class WorkoutSessionOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    check_in_id: uuid.UUID | None
    started_at: datetime
    finished_at: datetime | None
    effort_band: str | None
    program_id: uuid.UUID | None = None
    day_index: int | None = None
    sets: list[WorkoutSetOut]


async def _to_session_out(
    session: AsyncSession, workout_session: WorkoutSession
) -> WorkoutSessionOut:
    result = await session.execute(
        select(WorkoutSet)
        .where(WorkoutSet.session_id == workout_session.id)
        .order_by(WorkoutSet.at)
    )
    return WorkoutSessionOut(
        id=workout_session.id,
        member_id=workout_session.member_id,
        check_in_id=workout_session.check_in_id,
        started_at=workout_session.started_at,
        finished_at=workout_session.finished_at,
        effort_band=workout_session.effort_band,
        program_id=workout_session.program_id,
        day_index=workout_session.day_index,
        sets=[WorkoutSetOut.model_validate(s) for s in result.scalars().all()],
    )


class CreateWorkoutSessionRequest(BaseModel):
    id: uuid.UUID | None = None
    member_id: uuid.UUID
    check_in_id: uuid.UUID | None = None
    started_at: datetime
    #: The plan and day being trained, so the next visit knows what follows.
    #: Optional: an offline client built before decision 53 omits them.
    program_id: uuid.UUID | None = None
    day_index: int | None = None


@router.post(
    "/workout-sessions", response_model=WorkoutSessionOut, status_code=status.HTTP_201_CREATED
)
async def create_workout_session(
    body: CreateWorkoutSessionRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> WorkoutSessionOut:
    member = await session.get(Member, body.member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if body.check_in_id is not None and await session.get(CheckIn, body.check_in_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Check-in not found")
    if body.program_id is not None:
        program = await session.get(MemberProgram, body.program_id)
        if program is None or program.member_id != body.member_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "That plan is not this member's"
            )
        if body.day_index is not None and not 0 <= body.day_index < max(1, len(program.days)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The plan has no such day")

    workout_session = WorkoutSession(
        id=body.id or uuid.uuid4(),
        gym_id=claims.gym_id,
        member_id=body.member_id,
        check_in_id=body.check_in_id,
        started_at=body.started_at,
        program_id=body.program_id,
        day_index=body.day_index if body.program_id is not None else None,
    )
    session.add(workout_session)
    await session.flush()
    return await _to_session_out(session, workout_session)


@router.get("/workout-sessions/{session_id}", response_model=WorkoutSessionOut)
async def get_workout_session(session_id: uuid.UUID, session: CurrentSession) -> WorkoutSessionOut:
    workout_session = await session.get(WorkoutSession, session_id)
    if workout_session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout session not found")
    return await _to_session_out(session, workout_session)


class FinishWorkoutSessionRequest(BaseModel):
    finished_at: datetime
    effort_band: str | None = None


@router.patch("/workout-sessions/{session_id}", response_model=WorkoutSessionOut)
async def finish_workout_session(
    session_id: uuid.UUID,
    body: FinishWorkoutSessionRequest,
    session: CurrentSession,
    _claims: AccessTokenClaims = ManagerOrCoach,
) -> WorkoutSessionOut:
    workout_session = await session.get(WorkoutSession, session_id)
    if workout_session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout session not found")
    workout_session.finished_at = body.finished_at
    if body.effort_band is not None:
        workout_session.effort_band = body.effort_band
    await session.flush()
    return await _to_session_out(session, workout_session)


class LogSetRequest(BaseModel):
    id: uuid.UUID | None = None
    exercise_id: uuid.UUID
    set_number: int
    reps: int
    weight_kg: float
    machine_id: uuid.UUID | None = None
    at: datetime


@router.post(
    "/workout-sessions/{session_id}/sets",
    response_model=WorkoutSetOut,
    status_code=status.HTTP_201_CREATED,
)
async def log_set(
    session_id: uuid.UUID,
    body: LogSetRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> WorkoutSet:
    workout_session = await session.get(WorkoutSession, session_id)
    if workout_session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout session not found")
    if await session.get(Exercise, body.exercise_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    if body.machine_id is not None and await session.get(Machine, body.machine_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")

    workout_set = WorkoutSet(
        id=body.id or uuid.uuid4(),
        gym_id=claims.gym_id,
        session_id=session_id,
        member_id=workout_session.member_id,
        exercise_id=body.exercise_id,
        set_number=body.set_number,
        reps=body.reps,
        weight_kg=body.weight_kg,
        machine_id=body.machine_id,
        at=body.at,
    )
    session.add(workout_set)
    await session.flush()
    return workout_set


@router.get("/members/{member_id}/workout-sessions", response_model=list[WorkoutSessionOut])
async def list_workout_sessions(
    member_id: uuid.UUID,
    session: CurrentSession,
    claims: CurrentClaims,
    limit: int = 10,
) -> list[WorkoutSessionOut]:
    """Finished sessions only, most recent first — powers the coach's "last
    workout" summary (CoachMemberCard) and, since Phase 4 stage 6, a
    member's own session count. RLS already scopes this to the caller's
    gym; the 404 below is for a member id that doesn't exist at all, or —
    for a member caller — one that isn't their own (decision 28: a member
    token must never read another member's data by changing the id in
    the URL, and those two cases look identical from here, by design).
    """
    if claims.subject_type == "member" and claims.subject_id != member_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    result = await session.execute(
        select(WorkoutSession)
        .where(WorkoutSession.member_id == member_id, WorkoutSession.finished_at.is_not(None))
        .order_by(WorkoutSession.started_at.desc())
        .limit(limit)
    )
    return [await _to_session_out(session, s) for s in result.scalars().all()]


class TodayExerciseOut(BaseModel):
    program_exercise_id: uuid.UUID
    exercise_id: uuid.UUID
    exercise_name: dict[str, Any]
    order_index: int
    sets: int
    reps: dict[str, Any]
    target_weight_kg: float | None
    last_weight_kg: float | None


class TodayWorkoutOut(BaseModel):
    program_id: uuid.UUID | None
    program_title: dict[str, Any] | None
    exercises: list[TodayExerciseOut]
    open_session_id: uuid.UUID | None
    #: Which day these exercises are, of how many, and every day's title,
    #: so a coach can see "Day 2 of 3 — Pull" and switch. Decision 53.
    day_index: int = 0
    day_count: int = 1
    days: list[dict[str, Any]] = []


async def _due_day(
    session: AsyncSession,
    program: MemberProgram,
    open_session: WorkoutSession | None,
) -> int:
    """The day this member is due on this plan. A session already open on
    it keeps its day — refreshing mid-workout must not jump to the next one.
    Otherwise the day after the last session that logged at least one set:
    one that was opened and abandoned did not train anything."""
    day_count = max(1, len(program.days))
    if (
        open_session is not None
        and open_session.program_id == program.id
        and open_session.day_index is not None
        and open_session.day_index < day_count
    ):
        return open_session.day_index
    last = (
        await session.execute(
            select(WorkoutSession.day_index)
            .where(
                WorkoutSession.program_id == program.id,
                WorkoutSession.day_index.is_not(None),
                exists().where(WorkoutSet.session_id == WorkoutSession.id),
            )
            .order_by(WorkoutSession.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return next_day(day_count, last)


@router.get("/members/{member_id}/today-workout", response_model=TodayWorkoutOut)
async def get_today_workout(
    member_id: uuid.UUID,
    session: CurrentSession,
    claims: CurrentClaims,
    day: Annotated[int | None, Query(ge=0)] = None,
) -> TodayWorkoutOut:
    """Powers CoachMemberCard's "today's workout" and, since Phase 4 stage
    7, a member's own MemberToday screen — decision 2's "broaden, don't
    duplicate" pattern. A member caller must be asking about themselves;
    the 404 below covers both a member id that doesn't exist and one that
    isn't the caller's own (decision 28), which look identical here by
    design."""
    if claims.subject_type == "member" and claims.subject_id != member_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    program = await _active_program(session, member_id)

    open_session = (
        await session.execute(
            select(WorkoutSession)
            .where(WorkoutSession.member_id == member_id, WorkoutSession.finished_at.is_(None))
            .order_by(WorkoutSession.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if program is None:
        return TodayWorkoutOut(
            program_id=None, program_title=None, exercises=[],
            open_session_id=open_session.id if open_session else None,
        )

    day_count = max(1, len(program.days))
    # `?day=` is the coach choosing a different day than the one due; one
    # the plan no longer has falls back to the due day rather than erroring.
    day_index = day if day is not None and day < day_count else await _due_day(
        session, program, open_session
    )
    rows = (
        await session.execute(
            select(ProgramExercise, Exercise.name)
            .join(Exercise, Exercise.id == ProgramExercise.exercise_id)
            .where(
                ProgramExercise.program_id == program.id,
                ProgramExercise.day_index == day_index,
            )
            .order_by(ProgramExercise.order_index)
        )
    ).all()
    program_exercises = [
        ProgramExerciseRow(
            id=pe.id, exercise_id=pe.exercise_id, exercise_name=exercise_name,
            order_index=pe.order_index, sets=pe.sets, reps=pe.reps,
            target_weight_kg=(
                float(pe.target_weight_kg) if pe.target_weight_kg is not None else None
            ),
        )
        for pe, exercise_name in rows
    ]

    exercise_ids = [pe.exercise_id for pe in program_exercises]
    last_weights: dict[uuid.UUID, float] = {}
    if exercise_ids:
        weight_rows = (
            await session.execute(
                select(WorkoutSet.exercise_id, WorkoutSet.weight_kg)
                .distinct(WorkoutSet.exercise_id)
                .where(WorkoutSet.member_id == member_id, WorkoutSet.exercise_id.in_(exercise_ids))
                .order_by(WorkoutSet.exercise_id, WorkoutSet.at.desc())
            )
        ).all()
        last_weights = {exercise_id: float(weight_kg) for exercise_id, weight_kg in weight_rows}

    exercises = resolve_today_workout(program_exercises, last_weights)

    return TodayWorkoutOut(
        program_id=program.id,
        program_title=program.title,
        exercises=[
            TodayExerciseOut(
                program_exercise_id=e.program_exercise_id, exercise_id=e.exercise_id,
                exercise_name=e.exercise_name, order_index=e.order_index, sets=e.sets,
                reps=e.reps, target_weight_kg=e.target_weight_kg, last_weight_kg=e.last_weight_kg,
            )
            for e in exercises
        ],
        open_session_id=open_session.id if open_session else None,
        day_index=day_index,
        day_count=day_count,
        days=program.days,
    )
