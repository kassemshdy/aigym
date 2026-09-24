import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Member(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("gym_id", "phone"),)

    name: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    #: ``active`` or ``left``. Without it, a member who quit stays in the
    #: lapsed list forever and keeps accruing dues nobody will ever collect,
    #: so both figures the sales guarantee is settled on drift upward as a
    #: gym loses people — the opposite of what they measure. Decision 43.
    #:
    #: A leaver is **not** deleted: their attendance and payments are the
    #: history the dashboard is computed from, and their progress photos are
    #: theirs (decision 11). They stop being counted, not erased.
    #:
    #: There is deliberately no ``paused`` here. A freeze — travelling,
    #: injured, Ramadan — is a different thing: it moves a subscription's end
    #: date rather than removing someone from the roster, and conflating the
    #: two would mean a frozen member silently stopped counting as active.
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="active", default="active"
    )
    #: When they left, so "how many left this quarter" is answerable. Null
    #: while active, and cleared again if they come back.
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MemberProfile(Base, GymScopedMixin, TimestampMixin):
    """1:1 with Member. Split out because it's a different write pattern (a
    coach edits it occasionally) from Member itself (front desk, rarely)."""

    __tablename__ = "member_profiles"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    goal: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False)
    height_cm: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 1, asdecimal=False), nullable=False)
    body_fat: Mapped[float | None] = mapped_column(Numeric(4, 1, asdecimal=False), nullable=True)
    injuries: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    job: Mapped[str] = mapped_column(String, nullable=False)
    sleep_hours: Mapped[float] = mapped_column(Numeric(3, 1, asdecimal=False), nullable=False)
    weight_trend: Mapped[list[float]] = mapped_column(JSONB, nullable=False, default=list)
    # Set only by an approved ai_plan_drafts row (kind='nutrition') — never
    # directly by the member themselves. Null means "no AI-approved target
    # yet," not zero; Food.tsx falls back to a hardcoded default until set.
    daily_kcal_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
