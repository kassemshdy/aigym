"""Coaches, the fixed weekly class schedule, and a member's own private/
intro session bookings — reuses the models Phase 3 already seeded
(app/models/floor.py), no new schema. Coaches and classes are read by any
authenticated caller (staff browsing, or a member picking who to book);
bookings and attendance are member-scoped by claims.subject_id, never a
URL parameter (decision 28).
"""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentClaims, CurrentMember, CurrentSession
from app.models import Attendance, Booking, Coach, GymClass

router = APIRouter(tags=["booking"])


class CoachOut(BaseModel):
    id: uuid.UUID
    name: dict[str, str]
    speciality: dict[str, str]

    model_config = {"from_attributes": True}


@router.get("/coaches", response_model=list[CoachOut])
async def list_coaches(session: CurrentSession, _claims: CurrentClaims) -> list[Coach]:
    result = await session.execute(select(Coach))
    return list(result.scalars().all())


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
