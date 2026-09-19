"""Serves member-uploaded photos (progress photos, food entries) out of
app/storage.py's Railway Volume. Keys are unguessable (a random UUID), but
access is still gated by ownership/sharing, not key secrecy alone — a
wrong or forbidden key returns 404, same as every other cross-tenant
lookup in this product, never a 403 that would confirm the key is real.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from app import storage
from app.deps import CurrentClaims, CurrentSession
from app.models import FoodEntry, ProgressPhoto

router = APIRouter(tags=["media"])


@router.post("/media", status_code=status.HTTP_201_CREATED)
async def upload_media(file: UploadFile, _claims: CurrentClaims) -> dict[str, str]:
    """The upload half of app/storage.py — any authenticated caller can
    use it (a member uploading their own food/progress photo today; staff
    have no use for it yet but nothing stops them). The resulting key is
    an orphan until a food-entry or progress-photo write references it —
    that write, not this upload, is what decides who may ever see it via
    GET /media/{key}."""
    data = await file.read()
    try:
        key = await asyncio.to_thread(storage.save, data, file.content_type or "")
    except storage.UnsupportedContentType as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported content type"
        ) from exc
    return {"key": key}


@router.get("/media/{key}")
async def get_media(key: str, session: CurrentSession, claims: CurrentClaims) -> Response:
    photo = (
        await session.execute(select(ProgressPhoto).where(ProgressPhoto.photo_key == key))
    ).scalar_one_or_none()

    if photo is not None:
        # Decision 11: private by default, shared only per-photo and
        # explicitly.
        owns_it = claims.subject_type == "member" and claims.subject_id == photo.member_id
        staff_can_see = claims.subject_type == "staff" and photo.shared_with_coach
        if not (owns_it or staff_can_see):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    else:
        food_entry = (
            await session.execute(select(FoodEntry).where(FoodEntry.photo_key == key))
        ).scalar_one_or_none()
        if food_entry is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        # Food photos are "ordinary log data" (decision 11) — any staff at
        # the gym can see them, no per-photo sharing flag like progress
        # photos.
        owns_it = (
            claims.subject_type == "member" and claims.subject_id == food_entry.member_id
        )
        staff_can_see = claims.subject_type == "staff"
        if not (owns_it or staff_can_see):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    try:
        data = await asyncio.to_thread(storage.read, key)
    except storage.InvalidKey as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found") from exc
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    return Response(content=data, media_type=storage.content_type_for(key))
