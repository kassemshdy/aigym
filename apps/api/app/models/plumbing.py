from typing import Any

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import GymScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class IdempotencyKey(Base, UUIDPrimaryKeyMixin, GymScopedMixin, TimestampMixin):
    """Backs the Idempotency-Key middleware (stage 4). A repeat of the same
    key with the same request body replays response_body/response_status
    instead of re-running the write; a different body is a 409."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("gym_id", "key"),)

    key: Mapped[str] = mapped_column(String, nullable=False)
    request_hash: Mapped[str] = mapped_column(String, nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
