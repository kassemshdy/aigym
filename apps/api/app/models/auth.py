import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RefreshToken(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """One row per issued refresh token, keyed by the jti embedded in the
    token itself (app/security/jwt.py). Gym-scoped and RLS-protected like
    every other table here: /auth/refresh decodes the token's signature
    first — proving its gym_id claim is authentic — and only then opens
    app.gym_id from that claim before touching this table. So RLS is
    checking a value the client cannot forge, not one it supplied on the
    request.
    """

    __tablename__ = "refresh_tokens"

    jti: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MemberLoginCode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The member-facing half of decision 13 (phone + 6-digit code, no
    password, no email). Deliberately NOT gym-scoped/RLS-protected, like
    gyms and staff_users: verifying a code is the one place the API has to
    look something up *before* it knows which gym it's talking to, since the
    member only supplies a phone number, never a gym id. gym_id is still
    stored here (denormalized from the member at issue time) so a match
    immediately tells the caller which gym to scope the resulting session
    to.
    """

    __tablename__ = "member_login_codes"

    gym_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gyms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phone: Mapped[str] = mapped_column(String, nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
