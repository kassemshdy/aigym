import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Gym(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The tenant. Deliberately outside Row-Level Security — a gym doesn't
    scope itself, and staff onboarding needs to read this table before any
    ``app.gym_id`` is set."""

    __tablename__ = "gyms"

    name: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class StaffUser(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A person who can log in as staff. Not gym-scoped: one staff account
    can hold a role at more than one gym via StaffGymRole, and login (by
    phone, before we know which gym) has to find this row without an
    ``app.gym_id`` set yet."""

    __tablename__ = "staff_users"

    phone: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    pin_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # Rate-limits POST /auth/staff/pin/reset — deliberately its own column
    # rather than reusing updated_at, which is also set at row creation:
    # that would wrongly block the first-ever reset on a freshly seeded or
    # onboarded account within the cooldown window. NULL until the first
    # reset, so a new account is never blocked by its own creation.
    pin_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StaffGymRole(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """Grants a staff user a role ('manager' | 'coach') at one gym. This IS
    gym-scoped and carries RLS, unlike its two parent tables."""

    __tablename__ = "staff_gym_roles"
    __table_args__ = (UniqueConstraint("staff_user_id", "gym_id"),)

    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
