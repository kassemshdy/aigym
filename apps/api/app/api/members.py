import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentSession, require_role
from app.domain.dues import DuesStatus, compute_dues
from app.domain.whatsapp import wa_link
from app.models import Attendance, Member, MemberProfile, Payment, Plan, Subscription
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["members"])

ManagerOrCoach = Depends(require_role("manager", "coach"))


async def _current_subscription(session: AsyncSession, member_id: uuid.UUID) -> Subscription | None:
    result = await session.execute(
        select(Subscription)
        .where(Subscription.member_id == member_id)
        .order_by(Subscription.ends_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _last_visit(session: AsyncSession, member_id: uuid.UUID) -> date | None:
    result = await session.execute(
        select(func.max(Attendance.date)).where(Attendance.member_id == member_id)
    )
    return result.scalar_one_or_none()


class DuesOut(BaseModel):
    status: DuesStatus
    owed_usd: float


class MemberOut(BaseModel):
    id: uuid.UUID
    name: str
    name_en: str
    phone: str
    joined_at: datetime
    plan_id: uuid.UUID | None
    plan_name: dict[str, Any] | None
    ends_at: datetime | None
    last_visit: date | None
    dues: DuesOut | None


class MemberProfileOut(BaseModel):
    goal: str
    level: str
    height_cm: int
    weight_kg: float
    body_fat: float | None
    injuries: list[Any]
    days_per_week: int
    job: str
    sleep_hours: float
    weight_trend: list[float]


class MemberDetailOut(MemberOut):
    profile: MemberProfileOut | None


async def _to_member_out(session: AsyncSession, member: Member) -> MemberOut:
    subscription = await _current_subscription(session, member.id)
    plan = await session.get(Plan, subscription.plan_id) if subscription else None
    dues = None
    if subscription is not None and plan is not None:
        info = compute_dues(
            ends_at=subscription.ends_at,
            plan_price_usd=float(plan.price_usd),
            plan_days=plan.days,
        )
        dues = DuesOut(status=info.status, owed_usd=info.owed_usd)
    return MemberOut(
        id=member.id,
        name=member.name,
        name_en=member.name_en,
        phone=member.phone,
        joined_at=member.joined_at,
        plan_id=plan.id if plan else None,
        plan_name=plan.name if plan else None,
        ends_at=subscription.ends_at if subscription else None,
        last_visit=await _last_visit(session, member.id),
        dues=dues,
    )


@router.get("/members", response_model=list[MemberOut])
async def list_members(session: CurrentSession) -> list[MemberOut]:
    result = await session.execute(select(Member).order_by(Member.name_en))
    return [await _to_member_out(session, m) for m in result.scalars().all()]


class LapsedMemberOut(BaseModel):
    id: uuid.UUID
    name: str
    name_en: str
    phone: str
    last_visit: date | None
    days_since_visit: int | None


@router.get("/members/lapsed", response_model=list[LapsedMemberOut])
async def lapsed_members(
    session: CurrentSession, min_days: Annotated[int, Query(ge=0)] = 14
) -> list[LapsedMemberOut]:
    """The GTM number: members 14+ days without a visit, or who have never
    checked in at all."""
    result = await session.execute(select(Member))
    members = result.scalars().all()
    today = date.today()

    out: list[LapsedMemberOut] = []
    for member in members:
        last_visit = await _last_visit(session, member.id)
        days_since = (today - last_visit).days if last_visit else None
        if days_since is None or days_since >= min_days:
            out.append(
                LapsedMemberOut(
                    id=member.id, name=member.name, name_en=member.name_en, phone=member.phone,
                    last_visit=last_visit, days_since_visit=days_since,
                )
            )
    out.sort(key=lambda m: (m.days_since_visit is not None, m.days_since_visit or 0), reverse=True)
    return out


@router.get("/members/{member_id}", response_model=MemberDetailOut)
async def get_member(member_id: uuid.UUID, session: CurrentSession) -> MemberDetailOut:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    base = await _to_member_out(session, member)
    profile = await session.get(MemberProfile, member_id)
    profile_out = (
        MemberProfileOut(
            goal=profile.goal, level=profile.level, height_cm=profile.height_cm,
            weight_kg=float(profile.weight_kg),
            body_fat=float(profile.body_fat) if profile.body_fat is not None else None,
            injuries=profile.injuries, days_per_week=profile.days_per_week, job=profile.job,
            sleep_hours=float(profile.sleep_hours), weight_trend=profile.weight_trend,
        )
        if profile is not None
        else None
    )
    return MemberDetailOut(**base.model_dump(), profile=profile_out)


class CreateMemberRequest(BaseModel):
    name: str
    name_en: str
    phone: str
    plan_id: uuid.UUID
    goal: str
    level: str
    height_cm: int
    weight_kg: float
    body_fat: float | None = None
    injuries: list[Any] = []
    days_per_week: int
    job: str
    sleep_hours: float


@router.post("/members", response_model=MemberDetailOut, status_code=status.HTTP_201_CREATED)
async def create_member(
    body: CreateMemberRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> MemberDetailOut:
    plan = await session.get(Plan, body.plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")

    now = datetime.now(UTC)
    member = Member(
        id=uuid.uuid4(), gym_id=claims.gym_id, name=body.name, name_en=body.name_en,
        phone=body.phone, joined_at=now,
    )
    session.add(member)
    await session.flush()

    session.add(
        MemberProfile(
            member_id=member.id, gym_id=claims.gym_id, goal=body.goal, level=body.level,
            height_cm=body.height_cm, weight_kg=body.weight_kg, body_fat=body.body_fat,
            injuries=body.injuries, days_per_week=body.days_per_week, job=body.job,
            sleep_hours=body.sleep_hours, weight_trend=[],
        )
    )
    session.add(
        Subscription(
            id=uuid.uuid4(), gym_id=claims.gym_id, member_id=member.id, plan_id=plan.id,
            starts_at=now, ends_at=now + timedelta(days=plan.days),
        )
    )
    await session.flush()

    return await get_member(member.id, session)


class UpdateMemberRequest(BaseModel):
    name: str | None = None
    name_en: str | None = None
    phone: str | None = None
    goal: str | None = None
    level: str | None = None
    height_cm: int | None = None
    weight_kg: float | None = None
    body_fat: float | None = None
    injuries: list[Any] | None = None
    days_per_week: int | None = None
    job: str | None = None
    sleep_hours: float | None = None


@router.patch("/members/{member_id}", response_model=MemberDetailOut)
async def update_member(
    member_id: uuid.UUID,
    body: UpdateMemberRequest,
    session: CurrentSession,
    _claims: AccessTokenClaims = ManagerOrCoach,
) -> MemberDetailOut:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    for field in ("name", "name_en", "phone"):
        value = getattr(body, field)
        if value is not None:
            setattr(member, field, value)

    profile = await session.get(MemberProfile, member_id)
    if profile is not None:
        for field in (
            "goal", "level", "height_cm", "weight_kg", "body_fat",
            "injuries", "days_per_week", "job", "sleep_hours",
        ):
            value = getattr(body, field)
            if value is not None:
                setattr(profile, field, value)

    await session.flush()
    return await get_member(member_id, session)


class RecordPaymentRequest(BaseModel):
    amount_usd: float
    method: str
    plan_id: uuid.UUID | None = None


@router.post("/members/{member_id}/payments", response_model=MemberDetailOut)
async def record_payment(
    member_id: uuid.UUID,
    body: RecordPaymentRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> MemberDetailOut:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    current = await _current_subscription(session, member_id)
    plan_id = body.plan_id or (current.plan_id if current else None)
    if plan_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No plan on file — pass plan_id")
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")

    now = datetime.now(UTC)
    session.add(
        Payment(
            id=uuid.uuid4(), gym_id=claims.gym_id, member_id=member_id,
            amount_usd=body.amount_usd, at=now, method=body.method,
            recorded_by_staff_id=claims.subject_id,
        )
    )
    # Renewing extends from whichever is later: the current end date (still
    # active) or now (already lapsed) — a payment today never backdates a
    # lapsed member's new period to a date in the past.
    period_start = max(current.ends_at, now) if current else now
    session.add(
        Subscription(
            id=uuid.uuid4(), gym_id=claims.gym_id, member_id=member_id, plan_id=plan.id,
            starts_at=period_start, ends_at=period_start + timedelta(days=plan.days),
        )
    )
    await session.flush()
    return await get_member(member_id, session)


@router.get("/members/{member_id}/whatsapp-reminder")
async def whatsapp_reminder(
    member_id: uuid.UUID, session: CurrentSession, lang: str = "ar"
) -> dict[str, str]:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    detail = await get_member(member_id, session)
    owed = detail.dues.owed_usd if detail.dues else 0.0
    name = member.name if lang == "ar" else member.name_en
    message = (
        f"مرحبا {name}، رح تعمل تذكير بسيط إنو المبلغ المتوجب عليك هو {owed}$. شكرا!"
        if lang == "ar"
        else f"Hi {name}, a quick reminder that you have ${owed} due. Thanks!"
    )
    return {"wa_link": wa_link(member.phone, message)}
