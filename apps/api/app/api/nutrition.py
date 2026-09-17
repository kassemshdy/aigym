"""Tap-first nutrition logging. `at` is client-set, same reasoning as
workout sessions/sets: a log made offline must sort by when it actually
happened, not when it finally reached the server.
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentSession, require_role
from app.models import Member, NutritionLog
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["nutrition"])

ManagerOrCoach = Depends(require_role("super_admin", "manager", "coach"))


class NutritionLogOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    at: datetime
    band: str
    meals: list[Any]
    source: str

    model_config = {"from_attributes": True}


class CreateNutritionLogRequest(BaseModel):
    id: uuid.UUID | None = None
    at: datetime
    band: str
    meals: list[Any] = []
    source: str


@router.post(
    "/members/{member_id}/nutrition-logs",
    response_model=NutritionLogOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_nutrition_log(
    member_id: uuid.UUID,
    body: CreateNutritionLogRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> NutritionLog:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    log = NutritionLog(
        id=body.id or uuid.uuid4(),
        gym_id=claims.gym_id,
        member_id=member_id,
        at=body.at,
        band=body.band,
        meals=body.meals,
        source=body.source,
        logged_by_staff_id=claims.subject_id,
    )
    session.add(log)
    await session.flush()
    return log


@router.get("/members/{member_id}/nutrition-logs", response_model=list[NutritionLogOut])
async def list_nutrition_logs(
    member_id: uuid.UUID,
    session: CurrentSession,
    on: Annotated[date | None, Query(description="Filter to logs on this calendar date")] = None,
) -> list[NutritionLog]:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    stmt = select(NutritionLog).where(NutritionLog.member_id == member_id)
    if on is not None:
        stmt = stmt.where(NutritionLog.at >= on, NutritionLog.at < on + timedelta(days=1))
    stmt = stmt.order_by(NutritionLog.at.desc())

    result = await session.execute(stmt)
    return list(result.scalars().all())
