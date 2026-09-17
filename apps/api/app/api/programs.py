"""A member's assigned workout plan. One flat, editable list of exercises —
no day-of-week rotation. Only one program per member is ever active;
assigning a new one archives the old one instead of deleting it, so a
workout_set logged against an archived program's exercise still resolves
(exercise_id points at the catalog, never at program_exercises)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentSession, require_role
from app.models import Exercise, Member, MemberProgram, ProgramExercise
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["programs"])

ManagerOrCoach = Depends(require_role("super_admin", "manager", "coach"))


class ProgramExerciseIn(BaseModel):
    exercise_id: uuid.UUID
    sets: int
    reps: dict[str, Any]
    target_weight_kg: float | None = None


class ProgramExerciseOut(BaseModel):
    id: uuid.UUID
    exercise_id: uuid.UUID
    exercise_name: dict[str, Any]
    order_index: int
    sets: int
    reps: dict[str, Any]
    target_weight_kg: float | None


class ProgramOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    title: dict[str, Any]
    archived_at: datetime | None
    exercises: list[ProgramExerciseOut]


async def _to_program_out(session: AsyncSession, program: MemberProgram) -> ProgramOut:
    result = await session.execute(
        select(ProgramExercise, Exercise.name)
        .join(Exercise, Exercise.id == ProgramExercise.exercise_id)
        .where(ProgramExercise.program_id == program.id)
        .order_by(ProgramExercise.order_index)
    )
    rows = result.all()
    return ProgramOut(
        id=program.id,
        member_id=program.member_id,
        title=program.title,
        archived_at=program.archived_at,
        exercises=[
            ProgramExerciseOut(
                id=pe.id,
                exercise_id=pe.exercise_id,
                exercise_name=exercise_name,
                order_index=pe.order_index,
                sets=pe.sets,
                reps=pe.reps,
                target_weight_kg=float(pe.target_weight_kg)
                if pe.target_weight_kg is not None
                else None,
            )
            for pe, exercise_name in rows
        ],
    )


async def _active_program(session: AsyncSession, member_id: uuid.UUID) -> MemberProgram | None:
    result = await session.execute(
        select(MemberProgram)
        .where(MemberProgram.member_id == member_id, MemberProgram.archived_at.is_(None))
        .order_by(MemberProgram.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/members/{member_id}/programs/active", response_model=ProgramOut | None)
async def get_active_program(member_id: uuid.UUID, session: CurrentSession) -> ProgramOut | None:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    program = await _active_program(session, member_id)
    return await _to_program_out(session, program) if program is not None else None


class CreateProgramRequest(BaseModel):
    title: dict[str, Any]
    exercises: list[ProgramExerciseIn]


@router.post(
    "/members/{member_id}/programs", response_model=ProgramOut, status_code=status.HTTP_201_CREATED
)
async def create_program(
    member_id: uuid.UUID,
    body: CreateProgramRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> ProgramOut:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    current = await _active_program(session, member_id)
    if current is not None:
        current.archived_at = datetime.now(UTC)

    program = MemberProgram(
        id=uuid.uuid4(),
        gym_id=claims.gym_id,
        member_id=member_id,
        title=body.title,
        created_by_staff_id=claims.subject_id,
    )
    session.add(program)
    await session.flush()  # program_exercises below reference the program just added

    for order_index, item in enumerate(body.exercises):
        exercise = await session.get(Exercise, item.exercise_id)
        if exercise is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Exercise {item.exercise_id} not found")
        session.add(
            ProgramExercise(
                id=uuid.uuid4(),
                gym_id=claims.gym_id,
                program_id=program.id,
                exercise_id=item.exercise_id,
                order_index=order_index,
                sets=item.sets,
                reps=item.reps,
                target_weight_kg=item.target_weight_kg,
            )
        )
    await session.flush()

    return await _to_program_out(session, program)


class ReplaceExercisesRequest(BaseModel):
    exercises: list[ProgramExerciseIn]


@router.patch("/programs/{program_id}/exercises", response_model=ProgramOut)
async def replace_program_exercises(
    program_id: uuid.UUID,
    body: ReplaceExercisesRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> ProgramOut:
    program = await session.get(MemberProgram, program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Program not found")

    await session.execute(delete(ProgramExercise).where(ProgramExercise.program_id == program_id))
    for order_index, item in enumerate(body.exercises):
        exercise = await session.get(Exercise, item.exercise_id)
        if exercise is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Exercise {item.exercise_id} not found")
        session.add(
            ProgramExercise(
                id=uuid.uuid4(),
                gym_id=claims.gym_id,
                program_id=program.id,
                exercise_id=item.exercise_id,
                order_index=order_index,
                sets=item.sets,
                reps=item.reps,
                target_weight_kg=item.target_weight_kg,
            )
        )
    await session.flush()

    return await _to_program_out(session, program)


class UpdateProgramRequest(BaseModel):
    title: dict[str, Any] | None = None
    archived: bool | None = None


@router.patch("/programs/{program_id}", response_model=ProgramOut)
async def update_program(
    program_id: uuid.UUID,
    body: UpdateProgramRequest,
    session: CurrentSession,
    _claims: AccessTokenClaims = ManagerOrCoach,
) -> ProgramOut:
    program = await session.get(MemberProgram, program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Program not found")

    if body.title is not None:
        program.title = body.title
    if body.archived is True:
        program.archived_at = datetime.now(UTC)
    elif body.archived is False:
        program.archived_at = None

    await session.flush()
    return await _to_program_out(session, program)
