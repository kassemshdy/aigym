import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
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

    # An app/storage.py key, served through GET /media/{key} like any other
    # upload. NULL means the gym has not set one and the client falls back
    # to the bundled logo. Deliberately not a URL: the same opaque-key,
    # checked-one-layer-up model every other image in this product uses,
    # rather than a second way to reference a picture.
    logo_key: Mapped[str | None] = mapped_column(String, nullable=True)

    # ---------------------------------------------------------------- billing
    # What *we* charge this gym, which is not the gym's own data and must
    # never reach it. There is no RLS on this table to lean on and no role
    # that helps: app/api/onboarding.py grants super_admin to every gym's
    # first account, so the owner would pass any role check on their own
    # billing row. The boundary is therefore the response models — GymOut
    # (app/api/gyms.py) selects branding only, and tests/test_billing.py
    # walks the whole OpenAPI schema to prove no staff-facing model ever
    # grew one of these fields.
    #
    # Tracked, not processed (decision 3's carried open question): Stripe
    # does not serve Lebanese businesses, so money changes hands out of
    # band and this records what was agreed and what has been paid.
    billing_status: Mapped[str] = mapped_column(String, nullable=False, server_default="trial")
    #: NULL until a price is agreed. USD only, like every other amount here.
    monthly_usd: Mapped[float | None] = mapped_column(
        Numeric(8, 2, asdecimal=False), nullable=True
    )
    #: The last day this gym is paid up to. NULL means never invoiced.
    paid_through: Mapped[date | None] = mapped_column(Date, nullable=True)
    billing_notes: Mapped[str | None] = mapped_column(String, nullable=True)


class StaffUser(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A person who can log in as staff. Not gym-scoped: one staff account
    can hold a role at more than one gym via StaffGymRole, and login (by
    username, before we know which gym) has to find this row without an
    ``app.gym_id`` set yet.

    ``username``/``password_hash`` are the login credential (decision 21).
    ``phone`` is kept — it's no longer how a staff member logs in, but it's
    still how POST /auth/staff/password/reset delivers a new one, over
    WhatsApp.
    """

    __tablename__ = "staff_users"

    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # Rate-limits POST /auth/staff/password/reset — deliberately its own
    # column rather than reusing updated_at, which is also set at row
    # creation: that would wrongly block the first-ever reset on a freshly
    # seeded or onboarded account within the cooldown window. NULL until
    # the first reset, so a new account is never blocked by its own
    # creation.
    password_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StaffGymRole(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """Grants a staff user a role ('manager' | 'coach') at one gym. This IS
    gym-scoped and carries RLS, unlike its two parent tables."""

    __tablename__ = "staff_gym_roles"
    __table_args__ = (UniqueConstraint("staff_user_id", "gym_id"),)

    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
