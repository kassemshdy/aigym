import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_owner_sessionmaker, tenant_session
from app.deps import CurrentClaims, CurrentSession, require_role
from app.domain.whatsapp import wa_link
from app.integrations.whatsapp_business import send_whatsapp_text
from app.models import Member, MemberLoginCode, RefreshToken, StaffGymRole, StaffUser
from app.security.hashing import hash_secret, verify_secret
from app.security.jwt import (
    AccessTokenClaims,
    InvalidTokenError,
    SubjectType,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


class PrincipalOut(BaseModel):
    subject_id: uuid.UUID
    gym_id: uuid.UUID
    subject_type: str
    role: str


async def _issue_tokens(
    session: AsyncSession,
    *,
    subject_id: uuid.UUID,
    gym_id: uuid.UUID,
    subject_type: SubjectType,
    role: str,
) -> TokenPair:
    """Mint a fresh access+refresh pair and record the refresh token's jti.
    Never calls session.commit() itself — the caller's tenant_session (or the
    CurrentSession dependency) owns the transaction and commits on clean
    exit; committing here would end that transaction early.
    """
    access = create_access_token(
        subject_id=subject_id, gym_id=gym_id, subject_type=subject_type, role=role
    )
    refresh, jti = create_refresh_token(
        subject_id=subject_id, gym_id=gym_id, subject_type=subject_type, role=role
    )
    settings = get_settings()
    session.add(
        RefreshToken(
            gym_id=gym_id,
            jti=jti,
            subject_id=subject_id,
            subject_type=subject_type,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    return TokenPair(access_token=access, refresh_token=refresh)


class StaffLoginRequest(BaseModel):
    phone: str
    pin: str


@router.post("/staff/login", response_model=TokenPair)
async def staff_login(body: StaffLoginRequest) -> TokenPair:
    async with tenant_session(None) as session:
        staff = (
            await session.execute(select(StaffUser).where(StaffUser.phone == body.phone))
        ).scalar_one_or_none()

    if staff is None or staff.pin_hash is None or not verify_secret(body.pin, staff.pin_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid phone or PIN")

    # staff_gym_roles IS RLS-protected (it's gym-scoped), but we don't know
    # which gym to scope into yet — that's what this query determines. Read
    # it via the owner connection, the one deliberate exception documented
    # on get_owner_sessionmaker. Single-gym MVP: take the first role: a
    # person with roles at more than one gym would need a gym picker this
    # product doesn't have yet.
    async with get_owner_sessionmaker()() as owner_session:
        roles = (
            await owner_session.execute(
                select(StaffGymRole).where(StaffGymRole.staff_user_id == staff.id)
            )
        ).scalars().all()

    if not roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has no gym access")
    role = roles[0]

    async with tenant_session(role.gym_id) as session:
        return await _issue_tokens(
            session, subject_id=staff.id, gym_id=role.gym_id, subject_type="staff", role=role.role
        )


class StaffPinResetRequest(BaseModel):
    phone: str


class StaffPinResetResponse(BaseModel):
    sent: bool


@router.post("/staff/pin/reset", response_model=StaffPinResetResponse)
async def reset_staff_pin(body: StaffPinResetRequest) -> StaffPinResetResponse:
    """Self-service PIN reset, delivered over the WhatsApp Business API
    (decision 20's narrow exception to decision 4 — see
    app/integrations/whatsapp_business.py) rather than a wa.me link: unlike
    every other WhatsApp message in this product, there's no human at a
    front desk to tap send for a staff member locked out of their own
    login. No auth required — that's the point of a reset endpoint — so
    it's rate-limited per phone via staff_users.pin_reset_at (NULL until
    the first reset, so a freshly created account's first reset is never
    blocked by its own creation — see that column's docstring) rather than
    a separate table. Always resets pin_hash immediately regardless of
    whether delivery succeeds: a staff member who can prove they hold the
    phone (the PIN literally goes nowhere else) is the auth.
    """
    async with tenant_session(None) as session:
        staff = (
            await session.execute(select(StaffUser).where(StaffUser.phone == body.phone))
        ).scalar_one_or_none()

        if staff is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No staff account with that phone")

        settings = get_settings()
        cooldown = timedelta(minutes=settings.staff_pin_reset_cooldown_minutes)
        now = datetime.now(UTC)
        if staff.pin_reset_at is not None and now - staff.pin_reset_at < cooldown:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, "PIN was reset recently — try again shortly"
            )

        new_pin = f"{secrets.randbelow(10_000):04d}"
        staff.pin_hash = hash_secret(new_pin)
        staff.pin_reset_at = now
        phone = staff.phone

    sent = await send_whatsapp_text(to=phone, body=f"Your AIGym manager PIN is {new_pin}.")
    return StaffPinResetResponse(sent=sent)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest) -> TokenPair:
    try:
        claims = decode_refresh_token(body.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc

    async with tenant_session(claims.gym_id) as session:
        row = (
            await session.execute(select(RefreshToken).where(RefreshToken.jti == claims.jti))
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if row is None or row.revoked_at is not None or row.expires_at < now:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked or expired")

        row.revoked_at = now  # rotate: this token is dead the instant it's used once
        return await _issue_tokens(
            session,
            subject_id=claims.subject_id,
            gym_id=claims.gym_id,
            subject_type=claims.subject_type,
            role=claims.role,
        )


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class MemberCodeResponse(BaseModel):
    wa_link: str


@router.post("/member/{member_id}/code", response_model=MemberCodeResponse)
async def request_member_code(
    member_id: uuid.UUID,
    session: CurrentSession,
    claims: AccessTokenClaims = Depends(require_role("manager", "coach")),
) -> MemberCodeResponse:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    settings = get_settings()
    recent_count = (
        await session.execute(
            select(func.count())
            .select_from(MemberLoginCode)
            .where(
                MemberLoginCode.member_id == member.id,
                MemberLoginCode.created_at > datetime.now(UTC) - timedelta(hours=1),
            )
        )
    ).scalar_one()
    if recent_count >= settings.member_code_rate_limit_per_hour:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many codes requested")

    code = _generate_code()
    session.add(
        MemberLoginCode(
            gym_id=claims.gym_id,
            member_id=member.id,
            phone=member.phone,
            code_hash=hash_secret(code),
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.member_code_ttl_minutes),
        )
    )

    ttl = settings.member_code_ttl_minutes
    message = f"Your AIGym login code is {code}. It expires in {ttl} minutes."
    return MemberCodeResponse(wa_link=wa_link(member.phone, message))


class MemberLoginRequest(BaseModel):
    phone: str
    code: str


@router.post("/member/login", response_model=TokenPair)
async def member_login(body: MemberLoginRequest) -> TokenPair:
    now = datetime.now(UTC)
    async with tenant_session(None) as session:
        candidates = (
            await session.execute(
                select(MemberLoginCode).where(
                    MemberLoginCode.phone == body.phone,
                    MemberLoginCode.used_at.is_(None),
                    MemberLoginCode.expires_at > now,
                )
            )
        ).scalars().all()
        matched = next((c for c in candidates if verify_secret(body.code, c.code_hash)), None)
        if matched is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")
        matched.used_at = now
        gym_id, member_id = matched.gym_id, matched.member_id

    async with tenant_session(gym_id) as session:
        return await _issue_tokens(
            session, subject_id=member_id, gym_id=gym_id, subject_type="member", role="member"
        )


@router.get("/me", response_model=PrincipalOut)
async def me(claims: CurrentClaims) -> PrincipalOut:
    return PrincipalOut(
        subject_id=claims.subject_id,
        gym_id=claims.gym_id,
        subject_type=claims.subject_type,
        role=claims.role,
    )
