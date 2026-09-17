import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentSession
from app.models import Machine

router = APIRouter(tags=["machines"])


class MachineOut(BaseModel):
    id: uuid.UUID
    name: dict[str, Any]
    area: str

    model_config = {"from_attributes": True}


@router.get("/machines", response_model=list[MachineOut])
async def list_machines(session: CurrentSession) -> list[Machine]:
    result = await session.execute(select(Machine).order_by(Machine.area))
    return list(result.scalars().all())
