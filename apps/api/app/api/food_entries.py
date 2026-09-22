"""A member's own food log (decision 12). Every route is scoped by
claims.subject_id from the verified member token, never a URL path
parameter — decision 28's member-scoping rule, since RLS only knows
"this gym," not "this member's own row." `at` is server-set: unlike
workout sets/nutrition-band check-ins, food-entry writes aren't part of
the offline outbox this phase (decision 28), so there's no offline-first
reason to trust a client-supplied timestamp.
"""

import asyncio
import base64
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal, cast

from anthropic.types import MessageParam
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app import storage
from app.ai.client import AiUnavailable, AnthropicNotConfigured, run_structured
from app.ai.models import HAIKU_MODEL
from app.deps import CurrentMember, CurrentSession
from app.models import FoodEntry

router = APIRouter(tags=["food-entries"])

_LANG_NAME = {"ar": "Arabic", "en": "English"}

_VISION_PERSONA = (
    "You are AIGym's food-photo recognition assistant for a Lebanese gym member. "
    "Identify the meal in the photo and give one best-guess estimate of its calories "
    "and macros, drawing on typical Lebanese/Levantine dishes and restaurant portions "
    "when the food looks local. Give a short meal label in {lang_name}. This is only a "
    "starting estimate — the member reviews and can correct every number before it's "
    "ever saved, so commit to a single reasonable guess rather than hedging."
)


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


class FoodEstimateRequest(BaseModel):
    photo_key: str
    lang: str = "en"


class FoodEstimateOut(BaseModel):
    label: str
    kcal: int
    protein: int
    carbs: int
    fat: int


@router.post("/members/me/food-entries/estimate", response_model=FoodEstimateOut)
async def estimate_food_entry(
    body: FoodEstimateRequest, claims: CurrentMember
) -> FoodEstimateOut:
    """No write happens here — decision 12's confirm step is untouched, this
    only drafts a guess for `Food.tsx`'s confirm card. `photo_key` is
    trusted the same way POST /media already is: any authenticated caller
    who holds it may use it, since it's an unguessable random key and,
    at this point, not yet linked to any food entry a DB-row ownership
    check could run against (see app/api/media.py)."""
    try:
        data = await asyncio.to_thread(storage.read, body.photo_key)
    except storage.InvalidKey as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found") from exc
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    media_type = cast(
        Literal["image/jpeg", "image/png", "image/webp"],
        storage.content_type_for(body.photo_key),
    )
    messages: list[MessageParam] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                },
                {
                    "type": "text",
                    "text": "What meal is this? Estimate its calories and macros.",
                },
            ],
        }
    ]

    lang_name = _LANG_NAME.get(body.lang, "English")
    try:
        return run_structured(
            model=HAIKU_MODEL,
            system=_VISION_PERSONA.format(lang_name=lang_name),
            messages=messages,
            response_model=FoodEstimateOut,
            max_tokens=256,
            purpose="food_vision",
            gym_id=claims.gym_id,
        )
    except AnthropicNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI assistant is not configured"
        ) from exc
    except AiUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI assistant is temporarily unavailable"
        ) from exc


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
