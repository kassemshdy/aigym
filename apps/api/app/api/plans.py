import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentSession
from app.models import Plan

router = APIRouter(tags=["plans"])


class PlanOut(BaseModel):
    id: uuid.UUID
    name: dict[str, Any]
    price_usd: float
    days: int

    model_config = {"from_attributes": True}


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(session: CurrentSession) -> list[Plan]:
    result = await session.execute(select(Plan).order_by(Plan.price_usd))
    return list(result.scalars().all())
