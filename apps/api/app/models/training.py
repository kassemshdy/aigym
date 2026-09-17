import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Exercise(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """The gym's exercise catalog. A program's exercises reference this by
    id; replacing a program's exercise list (PUT .../exercises) never
    touches this table, so logged history in workout_sets stays attributable
    to a real exercise even after a program is rewritten or archived."""

    __tablename__ = "exercises"

    name: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    muscle_group: Mapped[str] = mapped_column(String, nullable=False)
    video_url: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MemberProgram(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """A member's assigned plan: one flat list of exercises, no day-of-week
    rotation. Only one program per member is ever active — assigning a new
    one archives the old one instead of deleting it, so past sessions keep
    a sensible program to point back to."""

    __tablename__ = "member_programs"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProgramExercise(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "program_exercises"

    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("member_programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    target_weight_kg: Mapped[float | None] = mapped_column(
        Numeric(5, 1, asdecimal=False), nullable=True
    )


class WorkoutSession(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """id is exceptionally client-mintable (see docs/DECISIONS.md): a
    session started offline must be referenceable by the very next queued
    'log a set' request before any server round trip has happened.
    UUIDPrimaryKeyMixin's default=uuid.uuid4 only applies when the caller
    omits id, so this needs no special column handling — just an API layer
    that accepts an optional client-supplied id."""

    __tablename__ = "workout_sessions"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_in_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("check_ins.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effort_band: Mapped[str | None] = mapped_column(String, nullable=True)


class WorkoutSet(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """id is exceptionally client-mintable, same reason as WorkoutSession.
    member_id is denormalized off session_id (matches Payment.member_id
    precedent) so a per-member 'last weight for exercise X' query never
    needs a join through workout_sessions just to filter by member."""

    __tablename__ = "workout_sets"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercises.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 1, asdecimal=False), nullable=False)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("machines.id", ondelete="SET NULL"), nullable=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NutritionLog(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "nutrition_logs"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    band: Mapped[str] = mapped_column(String, nullable=False)
    meals: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String, nullable=False)
    logged_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )
