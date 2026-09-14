"""Front-desk check-ins. Minimal on purpose: this exists in stage 4 to give
the idempotency middleware a real write to prove itself against (the
plan's own verification method: "the same check-in posted three times
leaves one row"). Stage 5 builds out the rest of the manager surface
(members, payments, dues, the lapsed list) around it.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentSession, require_role
from app.models import CheckIn, Member
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["check-ins"])


class CheckInRequest(BaseModel):
    member_id: uuid.UUID


class CheckInOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    at: datetime
    status: str


@router.post("/check-ins", response_model=CheckInOut, status_code=status.HTTP_201_CREATED)
async def create_check_in(
    body: CheckInRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = Depends(require_role("manager", "coach")),
) -> CheckInOut:
    member = await session.get(Member, body.member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    check_in = CheckIn(
        id=uuid.uuid4(),
        gym_id=claims.gym_id,
        member_id=member.id,
        at=datetime.now(UTC),
        status="waiting",
    )
    session.add(check_in)
    await session.flush()

    return CheckInOut(
        id=check_in.id, member_id=check_in.member_id, at=check_in.at, status=check_in.status
    )


@router.get("/check-ins/today", response_model=list[CheckInOut])
async def list_todays_check_ins(session: CurrentSession) -> list[CheckInOut]:
    """The manager Home screen's 'came today' tile — the GTM-adjacent number
    that proves the front desk is actually using the app, not a spreadsheet."""
    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(CheckIn).where(CheckIn.at >= start_of_day).order_by(CheckIn.at.desc())
    )
    return [
        CheckInOut(id=c.id, member_id=c.member_id, at=c.at, status=c.status)
        for c in result.scalars().all()
    ]
