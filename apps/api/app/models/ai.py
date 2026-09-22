import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AiPlanDraft(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """Decision 10's authority mechanism: any AI-proposed change to a
    member's program or calorie target lands here, pending, and is never
    applied directly — regardless of whether a member's chat message or a
    coach's "generate" button produced it (one mechanism for both, decision
    31). `payload` is the machine-actionable proposal `apply_draft`
    (app/domain/ai_drafts.py) reads on approval; kind='tip' drafts carry
    none — status-only. `original` is set once, on the first coach edit
    before approval, and never overwritten again afterward — the whole of
    this phase's coach-edit feedback capture (decision 33): a diff against
    the final approved fields is recoverable for free, no separate
    training pipeline."""

    __tablename__ = "ai_plan_drafts"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 'chat_nutrition'|'chat_training'|'coach_plan'|'coach_nutrition'|'coach_recommendation'
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # 'plan'|'nutrition'|'tip'
    headline: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    decided_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    original: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
