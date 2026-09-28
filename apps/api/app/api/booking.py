"""Coaches, the fixed weekly class schedule, and a member's own private/
intro session bookings — reuses the models Phase 3 already seeded
(app/models/floor.py). Coaches and classes are read by any authenticated
caller (staff browsing, or a member picking who to book), and classes are
set by the gym's managers;
bookings and attendance are member-scoped by claims.subject_id, never a
URL parameter (decision 28).
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import BilingualName
from app.deps import CurrentClaims, CurrentMember, CurrentSession, require_role
from app.models import Attendance, Booking, Coach, GymClass, StaffGymRole, StaffUser
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["booking"])

ManagerOrAdmin = Depends(require_role("super_admin", "manager"))


class CoachOut(BaseModel):
    id: uuid.UUID
    name: dict[str, str]
    speciality: dict[str, str]

    model_config = {"from_attributes": True}


async def ensure_coach_profile(
    session: AsyncSession, *, gym_id: uuid.UUID, staff: StaffUser
) -> None:
    """Give a coach account its booking profile at this gym, once.

    Called wherever someone becomes a coach (POST /staff, a role change).
    Never removed when they stop being one: past bookings reference the
    row, and a booking cascades with its coach. list_coaches stops showing
    it instead. Decision 50.
    """
    existing = (
        await session.execute(select(Coach.id).where(Coach.staff_user_id == staff.id))
    ).first()
    if existing is None:
        session.add(
            Coach(
                id=uuid.uuid4(), gym_id=gym_id,
                name={"ar": staff.name, "en": staff.name},
                speciality={"ar": "", "en": ""},
                staff_user_id=staff.id,
            )
        )
        await session.flush()


@router.get("/coaches", response_model=list[CoachOut])
async def list_coaches(session: CurrentSession, _claims: CurrentClaims) -> list[CoachOut]:
    """Who a member can book: every current coach account at this gym, plus
    any coach profile not tied to an account.

    A profile tied to an account shows only while that person still holds
    the coach role here — removing a coach under Staff takes them off this
    list, while their past bookings keep pointing at the row. Their name
    is read from the account, so correcting it under Staff corrects it
    here too. Before decision 50 this returned every row, which on a live
    gym meant the three placeholder coaches the seed wrote and never the
    real ones.
    """
    rows = (
        await session.execute(
            select(Coach, StaffUser.name)
            .outerjoin(StaffUser, StaffUser.id == Coach.staff_user_id)
            .outerjoin(
                StaffGymRole,
                and_(
                    StaffGymRole.staff_user_id == Coach.staff_user_id,
                    StaffGymRole.gym_id == Coach.gym_id,
                ),
            )
            .where(or_(Coach.staff_user_id.is_(None), StaffGymRole.role == "coach"))
            .order_by(StaffUser.name)
        )
    ).all()
    return [
        CoachOut(
            id=coach.id,
            name={"ar": account_name, "en": account_name} if account_name else coach.name,
            speciality=coach.speciality,
        )
        for coach, account_name in rows
    ]


class GymClassOut(BaseModel):
    id: uuid.UUID
    title: dict[str, str]
    coach_id: uuid.UUID
    weekdays: list[int]
    time: str
    duration_min: int

    model_config = {"from_attributes": True}


@router.get("/classes", response_model=list[GymClassOut])
async def list_classes(session: CurrentSession, _claims: CurrentClaims) -> list[GymClass]:
    result = await session.execute(select(GymClass).order_by(GymClass.time))
    return list(result.scalars().all())


# ---------------------------------------------------------------------
# The weekly class schedule, set by the gym. Until decision 50 the only
# classes were the seed's placeholders, with no way to change them.
# ---------------------------------------------------------------------

Weekday = Annotated[int, Field(ge=0, le=6)]  # 0 = Sunday, as Date.getDay()
ClassTime = Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]
Duration = Annotated[int, Field(ge=10, le=240)]


def _distinct_days(days: list[int]) -> list[int]:
    if not days:
        raise ValueError("pick at least one day")
    return sorted(set(days))


class CreateClassRequest(BaseModel):
    title: BilingualName
    coach_id: uuid.UUID
    weekdays: list[Weekday]
    time: ClassTime
    duration_min: Duration

    @field_validator("weekdays")
    @classmethod
    def _days(cls, days: list[int]) -> list[int]:
        return _distinct_days(days)


class UpdateClassRequest(BaseModel):
    title: BilingualName | None = None
    coach_id: uuid.UUID | None = None
    weekdays: list[Weekday] | None = None
    time: ClassTime | None = None
    duration_min: Duration | None = None

    @field_validator("weekdays")
    @classmethod
    def _days(cls, days: list[int] | None) -> list[int] | None:
        return None if days is None else _distinct_days(days)


async def _require_coach(session: AsyncSession, coach_id: uuid.UUID) -> None:
    # RLS scopes coaches, so another gym's coach is the same 404 as none.
    if await session.get(Coach, coach_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No coach with that id at this gym")


@router.post("/classes", response_model=GymClassOut, status_code=status.HTTP_201_CREATED)
async def create_class(
    body: CreateClassRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrAdmin,
) -> GymClass:
    await _require_coach(session, body.coach_id)
    gym_class = GymClass(
        id=uuid.uuid4(), gym_id=claims.gym_id, title=body.title.model_dump(),
        coach_id=body.coach_id, weekdays=body.weekdays, time=body.time,
        duration_min=body.duration_min,
    )
    session.add(gym_class)
    await session.flush()
    return gym_class


@router.patch("/classes/{class_id}", response_model=GymClassOut)
async def update_class(
    class_id: uuid.UUID,
    body: UpdateClassRequest,
    session: CurrentSession,
    _claims: AccessTokenClaims = ManagerOrAdmin,
) -> GymClass:
    gym_class = await session.get(GymClass, class_id)
    if gym_class is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No class with that id at this gym")
    if body.coach_id is not None:
        await _require_coach(session, body.coach_id)
        gym_class.coach_id = body.coach_id
    if body.title is not None:
        gym_class.title = body.title.model_dump()
    if body.weekdays is not None:
        gym_class.weekdays = body.weekdays
    if body.time is not None:
        gym_class.time = body.time
    if body.duration_min is not None:
        gym_class.duration_min = body.duration_min
    await session.flush()
    return gym_class


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: uuid.UUID,
    session: CurrentSession,
    _claims: AccessTokenClaims = ManagerOrAdmin,
) -> None:
    """A class is a weekly slot, not a record of anything that happened —
    nothing references it, so removing it is a real delete."""
    gym_class = await session.get(GymClass, class_id)
    if gym_class is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No class with that id at this gym")
    await session.delete(gym_class)


class BookingOut(BaseModel):
    id: uuid.UUID
    coach_id: uuid.UUID
    date: date
    time: str
    kind: str
    status: str

    model_config = {"from_attributes": True}


class CreateBookingRequest(BaseModel):
    coach_id: uuid.UUID
    date: date
    time: str
    kind: str


@router.get("/members/me/bookings", response_model=list[BookingOut])
async def list_my_bookings(session: CurrentSession, claims: CurrentMember) -> list[Booking]:
    result = await session.execute(
        select(Booking).where(Booking.member_id == claims.subject_id).order_by(Booking.date)
    )
    return list(result.scalars().all())


@router.post("/members/me/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: CreateBookingRequest, session: CurrentSession, claims: CurrentMember
) -> Booking:
    booking = Booking(
        id=uuid.uuid4(),
        gym_id=claims.gym_id,
        member_id=claims.subject_id,
        coach_id=body.coach_id,
        date=body.date,
        time=body.time,
        kind=body.kind,
        status="booked",
    )
    session.add(booking)
    await session.flush()
    return booking


@router.patch("/members/me/bookings/{booking_id}", response_model=BookingOut)
async def cancel_booking(
    booking_id: uuid.UUID, session: CurrentSession, claims: CurrentMember
) -> Booking:
    booking = await session.get(Booking, booking_id)
    if booking is None or booking.member_id != claims.subject_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    booking.status = "cancelled"
    await session.flush()
    return booking


class AttendanceOut(BaseModel):
    date: date

    model_config = {"from_attributes": True}


@router.get("/members/me/attendance", response_model=list[AttendanceOut])
async def list_my_attendance(session: CurrentSession, claims: CurrentMember) -> list[Attendance]:
    result = await session.execute(
        select(Attendance)
        .where(Attendance.member_id == claims.subject_id)
        .order_by(Attendance.date.desc())
    )
    return list(result.scalars().all())
