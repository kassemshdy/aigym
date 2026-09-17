"""The gym's exercise catalog a program's rows reference. Read by any staff
role (a coach browses it while building a program); writes are staff-wide
too — a coach adding a missing exercise inline while editing a program is
the expected flow (see ProgramEditor in the frontend plan), not a
manager-only gate.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentSession, require_role
from app.models import Exercise
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["exercises"])

AnyStaff = Depends(require_role("super_admin", "manager", "coach"))


class ExerciseOut(BaseModel):
    id: uuid.UUID
    name: dict[str, Any]
    muscle_group: str
    video_url: str | None
    active: bool

    model_config = {"from_attributes": True}


@router.get("/exercises", response_model=list[ExerciseOut])
async def list_exercises(session: CurrentSession) -> list[Exercise]:
    result = await session.execute(
        select(Exercise).where(Exercise.active.is_(True)).order_by(Exercise.muscle_group)
    )
    return list(result.scalars().all())


class CreateExerciseRequest(BaseModel):
    name: dict[str, Any]
    muscle_group: str
    video_url: str | None = None


@router.post("/exercises", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    body: CreateExerciseRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = AnyStaff,
) -> Exercise:
    exercise = Exercise(
        id=uuid.uuid4(),
        gym_id=claims.gym_id,
        name=body.name,
        muscle_group=body.muscle_group,
        video_url=body.video_url,
        active=True,
    )
    session.add(exercise)
    await session.flush()
    return exercise


class UpdateExerciseRequest(BaseModel):
    name: dict[str, Any] | None = None
    muscle_group: str | None = None
    video_url: str | None = None
    active: bool | None = None


@router.patch("/exercises/{exercise_id}", response_model=ExerciseOut)
async def update_exercise(
    exercise_id: uuid.UUID,
    body: UpdateExerciseRequest,
    session: CurrentSession,
    _claims: AccessTokenClaims = AnyStaff,
) -> Exercise:
    exercise = await session.get(Exercise, exercise_id)
    if exercise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")

    for field in ("name", "muscle_group", "video_url", "active"):
        value = getattr(body, field)
        if value is not None:
            setattr(exercise, field, value)

    await session.flush()
    return exercise
