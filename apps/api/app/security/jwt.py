"""Access and refresh token encode/decode.

Claims always carry gym_id, subject_type and role (per the Phase 2 plan) —
even for staff, who aren't gym-scoped in the database, a token is always
scoped to the one gym the holder is acting as right now. A refresh token
additionally carries a jti: refresh() decodes and verifies the signature
first (proving the embedded gym_id is authentic, not client-supplied), THEN
opens app.gym_id from that claim before checking the matching
refresh_tokens row — so Row-Level Security is checking a value the caller
cannot forge.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Literal

import jwt

from app.settings import get_settings

SubjectType = Literal["staff", "member"]


@dataclass(frozen=True)
class AccessTokenClaims:
    subject_id: uuid.UUID
    gym_id: uuid.UUID
    subject_type: SubjectType
    role: str


@dataclass(frozen=True)
class RefreshTokenClaims:
    subject_id: uuid.UUID
    gym_id: uuid.UUID
    subject_type: SubjectType
    role: str
    jti: uuid.UUID


class InvalidTokenError(ValueError):
    pass


def _encode(payload: dict[str, str], ttl_seconds: int) -> str:
    settings = get_settings()
    now = int(time.time())
    full: dict[str, object] = {**payload, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(full, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(
    *, subject_id: uuid.UUID, gym_id: uuid.UUID, subject_type: SubjectType, role: str
) -> str:
    settings = get_settings()
    return _encode(
        {
            "sub": str(subject_id),
            "gym_id": str(gym_id),
            "subject_type": subject_type,
            "role": role,
            "typ": "access",
        },
        settings.access_token_minutes * 60,
    )


def create_refresh_token(
    *,
    subject_id: uuid.UUID,
    gym_id: uuid.UUID,
    subject_type: SubjectType,
    role: str,
    jti: uuid.UUID | None = None,
) -> tuple[str, uuid.UUID]:
    settings = get_settings()
    jti = jti or uuid.uuid4()
    token = _encode(
        {
            "sub": str(subject_id),
            "gym_id": str(gym_id),
            "subject_type": subject_type,
            "role": role,
            "jti": str(jti),
            "typ": "refresh",
        },
        settings.refresh_token_days * 24 * 3600,
    )
    return token, jti


def _decode_raw(token: str) -> dict[str, str]:
    settings = get_settings()
    try:
        decoded: dict[str, str] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    return decoded


def decode_access_token(token: str) -> AccessTokenClaims:
    data = _decode_raw(token)
    if data.get("typ") != "access":
        raise InvalidTokenError("not an access token")
    return AccessTokenClaims(
        subject_id=uuid.UUID(data["sub"]),
        gym_id=uuid.UUID(data["gym_id"]),
        subject_type=data["subject_type"],  # type: ignore[arg-type]
        role=data["role"],
    )


def decode_refresh_token(token: str) -> RefreshTokenClaims:
    data = _decode_raw(token)
    if data.get("typ") != "refresh":
        raise InvalidTokenError("not a refresh token")
    return RefreshTokenClaims(
        subject_id=uuid.UUID(data["sub"]),
        gym_id=uuid.UUID(data["gym_id"]),
        subject_type=data["subject_type"],  # type: ignore[arg-type]
        role=data["role"],
        jti=uuid.UUID(data["jti"]),
    )
