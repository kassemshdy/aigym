"""The member-facing video library (Phase 4). Any authenticated caller —
staff or member — can browse it; only staff can add or edit entries, same
split as app/api/exercises.py. Viewing a single video bumps its view_count
as a side effect (no separate endpoint for that).
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentClaims, CurrentSession, require_role
from app.models import Video
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["videos"])

AnyStaff = Depends(require_role("super_admin", "manager", "coach"))


class VideoOut(BaseModel):
    id: uuid.UUID
    title: dict[str, Any]
    provider: str
    external_id: str
    muscle_group: str
    equipment: str
    seconds: int
    view_count: int
    active: bool

    model_config = {"from_attributes": True}


@router.get("/videos", response_model=list[VideoOut])
async def list_videos(session: CurrentSession, _claims: CurrentClaims) -> list[Video]:
    result = await session.execute(
        select(Video).where(Video.active.is_(True)).order_by(Video.muscle_group)
    )
    return list(result.scalars().all())


@router.get("/videos/{video_id}", response_model=VideoOut)
async def get_video(
    video_id: uuid.UUID, session: CurrentSession, _claims: CurrentClaims
) -> Video:
    video = await session.get(Video, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
    video.view_count += 1
    await session.flush()
    return video


class CreateVideoRequest(BaseModel):
    title: dict[str, Any]
    provider: str
    external_id: str
    muscle_group: str
    equipment: str
    seconds: int


@router.post("/videos", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
async def create_video(
    body: CreateVideoRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = AnyStaff,
) -> Video:
    video = Video(
        id=uuid.uuid4(),
        gym_id=claims.gym_id,
        title=body.title,
        provider=body.provider,
        external_id=body.external_id,
        muscle_group=body.muscle_group,
        equipment=body.equipment,
        seconds=body.seconds,
        view_count=0,
        active=True,
        created_by_staff_id=claims.subject_id,
    )
    session.add(video)
    await session.flush()
    return video


class UpdateVideoRequest(BaseModel):
    title: dict[str, Any] | None = None
    muscle_group: str | None = None
    equipment: str | None = None
    active: bool | None = None


@router.patch("/videos/{video_id}", response_model=VideoOut)
async def update_video(
    video_id: uuid.UUID,
    body: UpdateVideoRequest,
    session: CurrentSession,
    _claims: AccessTokenClaims = AnyStaff,
) -> Video:
    video = await session.get(Video, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")

    for field in ("title", "muscle_group", "equipment", "active"):
        value = getattr(body, field)
        if value is not None:
            setattr(video, field, value)

    await session.flush()
    return video
