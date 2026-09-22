"""A member editing their own body/lifestyle profile — decision 28's
`/members/me/...` pattern, deliberately separate from staff's
`PATCH /members/{id}`: that endpoint also edits name/phone/plan-adjacent
fields no member should self-serve. `daily_kcal_target` is excluded from
the request body entirely — it's coach/AI-approval-only
(app/api/ai_drafts.py), never something a member can raise by editing
their own profile.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.deps import CurrentMember, CurrentSession
from app.models import MemberProfile
from app.schemas.injuries import MemberInjury

router = APIRouter(tags=["member-profile"])


class UpdateMyProfileRequest(BaseModel):
    goal: str | None = None
    level: str | None = None
    height_cm: int | None = None
    weight_kg: float | None = None
    body_fat: float | None = None
    injuries: list[MemberInjury] | None = None
    days_per_week: int | None = None
    job: str | None = None
    sleep_hours: float | None = None


class UpdateMyProfileOut(BaseModel):
    goal: str
    level: str
    height_cm: int
    weight_kg: float
    body_fat: float | None
    injuries: list[MemberInjury]
    days_per_week: int
    job: str
    sleep_hours: float
    weight_trend: list[float]
    daily_kcal_target: int | None


@router.patch("/members/me/profile", response_model=UpdateMyProfileOut)
async def update_my_profile(
    body: UpdateMyProfileRequest, session: CurrentSession, claims: CurrentMember
) -> UpdateMyProfileOut:
    profile = await session.get(MemberProfile, claims.subject_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")

    for field in (
        "goal", "level", "height_cm", "weight_kg", "body_fat",
        "days_per_week", "job", "sleep_hours",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(profile, field, value)
    if body.injuries is not None:
        profile.injuries = [i.model_dump() for i in body.injuries]

    await session.flush()
    return UpdateMyProfileOut(
        goal=profile.goal, level=profile.level, height_cm=profile.height_cm,
        weight_kg=float(profile.weight_kg),
        body_fat=float(profile.body_fat) if profile.body_fat is not None else None,
        injuries=profile.injuries, days_per_week=profile.days_per_week, job=profile.job,
        sleep_hours=float(profile.sleep_hours), weight_trend=profile.weight_trend,
        daily_kcal_target=profile.daily_kcal_target,
    )
