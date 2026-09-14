import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Plan(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "plans"

    name: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    price_usd: Mapped[float] = mapped_column(Numeric(8, 2, asdecimal=False), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)


class Subscription(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """One membership period. A member's *current* plan and end date are the
    subscription with the latest ``ends_at`` — never stored redundantly on
    Member, per docs/DECISIONS.md (dues stay derived)."""

    __tablename__ = "subscriptions"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Payment(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    __tablename__ = "payments"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_usd: Mapped[float] = mapped_column(Numeric(8, 2, asdecimal=False), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    recorded_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )
