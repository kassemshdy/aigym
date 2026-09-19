"""A member's own progress photos (decision 11): private by default,
sharing is per-photo and explicit, deletion is real — the stored object
goes too, not just the row. Every route is scoped by claims.subject_id
from the verified member token, never a URL path parameter (decision 28).
"""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app import storage
from app.deps import CurrentMember, CurrentSession, require_role
from app.models import Member, ProgressPhoto
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["progress-photos"])

AnyStaff = Depends(require_role("super_admin", "manager", "coach"))


class ProgressPhotoOut(BaseModel):
    id: uuid.UUID
    at: datetime
    photo_key: str
    shared_with_coach: bool

    model_config = {"from_attributes": True}


class CreateProgressPhotoRequest(BaseModel):
    photo_key: str


@router.post(
    "/members/me/progress-photos",
    response_model=ProgressPhotoOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_progress_photo(
    body: CreateProgressPhotoRequest, session: CurrentSession, claims: CurrentMember
) -> ProgressPhoto:
    photo = ProgressPhoto(
        id=uuid.uuid4(),
        gym_id=claims.gym_id,
        member_id=claims.subject_id,
        at=datetime.now(UTC),
        photo_key=body.photo_key,
        # Decision 11: private by default, never created pre-shared.
        shared_with_coach=False,
    )
    session.add(photo)
    await session.flush()
    return photo


@router.get("/members/me/progress-photos", response_model=list[ProgressPhotoOut])
async def list_progress_photos(
    session: CurrentSession, claims: CurrentMember
) -> list[ProgressPhoto]:
    stmt = (
        select(ProgressPhoto)
        .where(ProgressPhoto.member_id == claims.subject_id)
        .order_by(ProgressPhoto.at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


class UpdateProgressPhotoRequest(BaseModel):
    shared_with_coach: bool


@router.patch("/members/me/progress-photos/{photo_id}", response_model=ProgressPhotoOut)
async def update_progress_photo(
    photo_id: uuid.UUID,
    body: UpdateProgressPhotoRequest,
    session: CurrentSession,
    claims: CurrentMember,
) -> ProgressPhoto:
    photo = await session.get(ProgressPhoto, photo_id)
    if photo is None or photo.member_id != claims.subject_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    photo.shared_with_coach = body.shared_with_coach
    await session.flush()
    return photo


@router.delete("/members/me/progress-photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_progress_photo(
    photo_id: uuid.UUID, session: CurrentSession, claims: CurrentMember
) -> None:
    photo = await session.get(ProgressPhoto, photo_id)
    if photo is None or photo.member_id != claims.subject_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    key = photo.photo_key
    await session.delete(photo)
    await session.flush()
    # Real deletion, not just the row — decision 11 is explicit about this.
    await asyncio.to_thread(storage.delete, key)


@router.get("/members/{member_id}/shared-photos", response_model=list[ProgressPhotoOut])
async def list_shared_photos(
    member_id: uuid.UUID,
    session: CurrentSession,
    _claims: AccessTokenClaims = AnyStaff,
) -> list[ProgressPhoto]:
    """The one staff-facing read of this data (decision 11): only rows the
    member explicitly shared, nothing auto-loads, and it never returns a
    private photo — the WHERE clause is the enforcement, not a UI choice."""
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    stmt = (
        select(ProgressPhoto)
        .where(ProgressPhoto.member_id == member_id, ProgressPhoto.shared_with_coach.is_(True))
        .order_by(ProgressPhoto.at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
