"""A member's own food log (decision 12). Every route is scoped by
claims.subject_id from the verified member token, never a URL path
parameter — decision 28's member-scoping rule, since RLS only knows
"this gym," not "this member's own row." `at` is server-set: unlike
workout sets/nutrition-band check-ins, food-entry writes aren't part of
the offline outbox this phase (decision 28), so there's no offline-first
reason to trust a client-supplied timestamp.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentMember, CurrentSession
from app.models import FoodEntry

router = APIRouter(tags=["food-entries"])


class FoodEntryOut(BaseModel):
    id: uuid.UUID
    at: datetime
    label: str
    kcal: int
    protein: int
    carbs: int
    fat: int
    source: str
    photo_key: str | None
    estimate: dict[str, Any] | None

    model_config = {"from_attributes": True}


class CreateFoodEntryRequest(BaseModel):
    label: str
    kcal: int
    protein: int
    carbs: int
    fat: int
    source: str
    photo_key: str | None = None
    estimate: dict[str, Any] | None = None


@router.post(
    "/members/me/food-entries", response_model=FoodEntryOut, status_code=status.HTTP_201_CREATED
)
async def create_food_entry(
    body: CreateFoodEntryRequest, session: CurrentSession, claims: CurrentMember
) -> FoodEntry:
    entry = FoodEntry(
        id=uuid.uuid4(),
        gym_id=claims.gym_id,
        member_id=claims.subject_id,
        at=datetime.now(UTC),
        label=body.label,
        kcal=body.kcal,
        protein=body.protein,
        carbs=body.carbs,
        fat=body.fat,
        source=body.source,
        photo_key=body.photo_key,
        estimate=body.estimate,
    )
    session.add(entry)
    await session.flush()
    return entry


@router.get("/members/me/food-entries", response_model=list[FoodEntryOut])
async def list_food_entries(
    session: CurrentSession,
    claims: CurrentMember,
    on: Annotated[date | None, Query(description="Filter to entries on this calendar date")] = None,
) -> list[FoodEntry]:
    stmt = select(FoodEntry).where(FoodEntry.member_id == claims.subject_id)
    if on is not None:
        stmt = stmt.where(FoodEntry.at >= on, FoodEntry.at < on + timedelta(days=1))
    stmt = stmt.order_by(FoodEntry.at.desc())

    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.delete("/members/me/food-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_entry(
    entry_id: uuid.UUID, session: CurrentSession, claims: CurrentMember
) -> None:
    entry = await session.get(FoodEntry, entry_id)
    if entry is None or entry.member_id != claims.subject_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await session.delete(entry)
