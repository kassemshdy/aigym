import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CheckIn(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """Today's front-desk queue. Transient — status moves waiting -> training
    -> done over the course of a visit."""

    __tablename__ = "check_ins"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="waiting")


class Attendance(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """One row per member per day they showed up. The historical record the
    lapsed-members list and attendance heatmap read from — check_ins is not
    kept long enough to answer 'last visit'."""

    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("gym_id", "member_id", "date"),)

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)


class Machine(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "machines"

    name: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    area: Mapped[str] = mapped_column(String, nullable=False)


class Coach(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "coaches"

    name: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    speciality: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    staff_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )


class GymClass(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "classes"

    title: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    coach_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coaches.id", ondelete="RESTRICT"), nullable=False
    )
    weekdays: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    time: Mapped[str] = mapped_column(String, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)


class Booking(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "bookings"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    coach_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coaches.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="booked")
