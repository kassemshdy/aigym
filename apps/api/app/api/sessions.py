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
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.programs import _active_program
from app.deps import CurrentSession, require_role
from app.domain.workout import ProgramExerciseRow, resolve_today_workout
from app.models import (
    CheckIn,
    Exercise,
    Machine,
    Member,
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
        sets=[WorkoutSetOut.model_validate(s) for s in result.scalars().all()],
    )


class CreateWorkoutSessionRequest(BaseModel):
    id: uuid.UUID | None = None
    member_id: uuid.UUID
    check_in_id: uuid.UUID | None = None
    started_at: datetime


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

    workout_session = WorkoutSession(
        id=body.id or uuid.uuid4(),
        gym_id=claims.gym_id,
        member_id=body.member_id,
        check_in_id=body.check_in_id,
        started_at=body.started_at,
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
    limit: int = 10,
) -> list[WorkoutSessionOut]:
    """Finished sessions only, most recent first — powers the coach's "last
    workout" summary (CoachMemberCard). RLS already scopes this to the
    caller's gym; the 404 below is for a member id that doesn't exist at
    all, not a cross-gym one (those look identical from here, by design).
    """
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


@router.get("/members/{member_id}/today-workout", response_model=TodayWorkoutOut)
async def get_today_workout(member_id: uuid.UUID, session: CurrentSession) -> TodayWorkoutOut:
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

    rows = (
        await session.execute(
            select(ProgramExercise, Exercise.name)
            .join(Exercise, Exercise.id == ProgramExercise.exercise_id)
            .where(ProgramExercise.program_id == program.id)
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
    )
