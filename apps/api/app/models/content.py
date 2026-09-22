import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Video(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """The member-facing video library (Phase 4) — distinct from
    Exercise.video_url (Phase 3's single per-exercise link, still used by
    ProgramEditor). provider + external_id keep decision 5's hand-built
    unlisted-embed approach reversible without a live oEmbed fetch, which
    stays out of scope this phase (decision 28) — a coach enters
    title/muscle/equipment by hand, same as an exercise."""

    __tablename__ = "videos"

    title: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    muscle_group: Mapped[str] = mapped_column(String, nullable=False)
    equipment: Mapped[str] = mapped_column(String, nullable=False)
    seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )


class FoodEntry(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """A member's own food log (decision 12) — distinct from
    training.py's NutritionLog, which is the coach's workout-day
    calorie-*band* check-in, not the member's own entries. `label` is
    plain text, not a bilingual JSONB pair like catalog content (Exercise,
    Video): a member types their own meal in their own language, there is
    no second-language version to keep in sync. `estimate` carries the
    model's original guess alongside kcal/protein/carbs/fat (the member's
    confirmed-or-corrected numbers) for `source="photo"` rows — decision
    12's feedback-signal pair; drop it and every correction is thrown
    away. The vision estimate itself stays fake until Phase 5 — only the
    confirm-and-log step is real this phase."""

    __tablename__ = "food_entries"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    protein: Mapped[int] = mapped_column(Integer, nullable=False)
    carbs: Mapped[int] = mapped_column(Integer, nullable=False)
    fat: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    photo_key: Mapped[str | None] = mapped_column(String, nullable=True)
    estimate: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ProgressPhoto(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """Decision 11: `shared_with_coach` defaults false in the schema
    itself, not just the application, so no code path can accidentally
    invert it. Deletion (app/api/progress_photos.py, stage 5) removes the
    stored object via app/storage.py, not just this row."""

    __tablename__ = "progress_photos"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    photo_key: Mapped[str] = mapped_column(String, nullable=False)
    shared_with_coach: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
