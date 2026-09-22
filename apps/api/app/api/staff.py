import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentSession, require_role
from app.models import RefreshToken, StaffGymRole, StaffUser
from app.security.hashing import generate_password, hash_secret
from app.security.jwt import AccessTokenClaims

router = APIRouter(prefix="/staff", tags=["staff"])

ManagerOrAdmin = Depends(require_role("super_admin", "manager"))

#: Role changes are super_admin-only. Not an oversight of the flat-roles
#: trap in require_role's docstring — see change_staff_role for why a
#: manager has nothing legitimate to do here.
AdminOnly = Depends(require_role("super_admin"))


class CreateStaffRequest(BaseModel):
    username: str
    password: str
    name: str
    phone: str
    role: Literal["manager", "coach", "super_admin"]


class StaffOut(BaseModel):
    id: uuid.UUID
    username: str
    name: str
    role: str


@router.get("", response_model=list[StaffOut])
async def list_staff(
    session: CurrentSession, _claims: AccessTokenClaims = ManagerOrAdmin
) -> list[StaffOut]:
    """Staff at the caller's own gym. StaffGymRole is RLS-scoped (decision
    16), so this join never needs an explicit gym_id filter; StaffUser
    itself carries none — it's the other deliberate RLS exception."""
    rows = (
        await session.execute(
            select(StaffUser, StaffGymRole.role).join(
                StaffGymRole, StaffGymRole.staff_user_id == StaffUser.id
            )
        )
    ).all()
    return [
        StaffOut(id=user.id, username=user.username, name=user.name, role=role)
        for user, role in rows
    ]


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
async def create_staff(
    body: CreateStaffRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrAdmin,
) -> StaffOut:
    """Decision 21, amended: a super_admin creates any staff account; a
    manager may only create coach accounts — creating another manager or a
    super_admin stays super_admin-only, so a manager can staff up the floor
    without being able to grant themselves or anyone else more access than
    they already have. A coach cannot reach this endpoint at all
    (require_role above excludes it). staff_users has no RLS (it's not
    gym-scoped, same as decision 16's other two exceptions), so the
    username-uniqueness check below is correctly global across every gym,
    not just this one.
    """
    if claims.role == "manager" and body.role != "coach":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Managers can only create coach accounts")

    existing = (
        await session.execute(select(StaffUser).where(StaffUser.username == body.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    staff = StaffUser(
        id=uuid.uuid4(),
        username=body.username,
        phone=body.phone,
        name=body.name,
        password_hash=hash_secret(body.password),
    )
    session.add(staff)
    await session.flush()  # staff_gym_roles.staff_user_id references staff just added above
    session.add(StaffGymRole(gym_id=claims.gym_id, staff_user_id=staff.id, role=body.role))

    return StaffOut(id=staff.id, username=staff.username, name=staff.name, role=body.role)


# ---------------------------------------------------------------------
# Phase 6 stage 5 — changing and revoking access, the gaps decision 25
# named as "real gaps if a coach ever needs to be let go, not just added".
#
# Every write below targets StaffGymRole and never StaffUser. That split is
# the whole design: the account is global (one person can coach at two
# gyms, and login has to find them before any gym is known), while the
# role is per-gym and RLS-protected. Deleting the account instead of the
# role would sign someone out of a gym this caller has no authority over,
# and would free their platform-unique username for someone else to claim.
# ---------------------------------------------------------------------


async def _staff_at_this_gym(
    session: AsyncSession, staff_user_id: uuid.UUID
) -> tuple[StaffUser, StaffGymRole]:
    """This person's account and their role at the caller's own gym, or 404.

    RLS scopes staff_gym_roles, so "no such person" and "works only at
    another gym" come back as the same 404 — which is the right answer to
    both: one gym has no business learning who is on another's payroll.
    """
    row = (
        await session.execute(
            select(StaffUser, StaffGymRole)
            .join(StaffGymRole, StaffGymRole.staff_user_id == StaffUser.id)
            .where(StaffUser.id == staff_user_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No staff member with that id at this gym")
    user, role = row
    return user, role


async def _revoke_refresh_tokens(session: AsyncSession, staff_user_id: uuid.UUID) -> None:
    """Kill every live refresh token this person holds *at this gym*.

    Without this a demoted manager keeps manager access for up to
    settings.refresh_token_days (30) simply by refreshing the token they
    already hold: the role is baked into a token when it is issued, and
    POST /auth/refresh copies it forward from the old token's claims
    rather than re-reading staff_gym_roles.

    It does not make the change instant, and it would be wrong to say it
    does. The access token in their hands right now still says `manager`
    until it expires (settings.access_token_minutes, 15). What this buys
    is a 15-minute window instead of a 30-day one.

    refresh_tokens is gym-scoped and RLS-protected, so this deliberately
    cannot reach the same person's session at another gym. Losing access
    here is not grounds for being signed out somewhere this caller has
    nothing to do with.
    """
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.subject_id == staff_user_id,
            RefreshToken.subject_type == "staff",
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )


async def _other_super_admins(session: AsyncSession, staff_user_id: uuid.UUID) -> int:
    """How many super_admins this gym would still have if this person
    stopped being one. RLS scopes the count to the caller's gym."""
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(StaffGymRole)
                .where(
                    StaffGymRole.role == "super_admin",
                    StaffGymRole.staff_user_id != staff_user_id,
                )
            )
        ).scalar_one()
    )


async def _guard_last_super_admin(
    session: AsyncSession, role: StaffGymRole, *, becoming: str | None
) -> None:
    """A gym that loses its last super_admin can never grant a role again —
    there is nobody left who is allowed to reach these endpoints, and no
    operator UI to repair it from (the plan keeps cross-gym administration
    to a script on purpose).

    Checked against the resulting state rather than against who is asking.
    That matters: a caller's access token still says `super_admin` for up
    to access_token_minutes after their own role was changed, so a rule
    phrased as "you must be a super_admin, so another one must exist" is
    not actually true at the moment it is enforced.
    """
    if role.role != "super_admin" or becoming == "super_admin":
        return
    if await _other_super_admins(session, role.staff_user_id) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This gym would be left with no super_admin"
        )


class UpdateStaffRoleRequest(BaseModel):
    role: Literal["manager", "coach", "super_admin"]


@router.patch("/{staff_user_id}", response_model=StaffOut)
async def change_staff_role(
    staff_user_id: uuid.UUID,
    body: UpdateStaffRoleRequest,
    session: CurrentSession,
    _claims: AccessTokenClaims = AdminOnly,
) -> StaffOut:
    """Change what someone is allowed to do at this gym.

    **super_admin only, deliberately.** Decision 25 lets a manager create
    coaches, and carrying that shape over to role changes leaves a manager
    with nothing legitimate to do: promoting a coach hands out access the
    manager was never given the authority to hand out, and demoting a
    manager or a super_admin is a manager acting against a peer or the
    owner. "coach → coach" is the only change that would be left, so the
    endpoint is closed to them rather than pretending to offer something.
    """
    user, role = await _staff_at_this_gym(session, staff_user_id)
    await _guard_last_super_admin(session, role, becoming=body.role)

    # Only on a real change: re-sending someone's current role should not
    # sign them out, and a UI that PATCHes a whole form would otherwise do
    # exactly that.
    if role.role != body.role:
        role.role = body.role
        await _revoke_refresh_tokens(session, staff_user_id)

    return StaffOut(id=user.id, username=user.username, name=user.name, role=body.role)


@router.delete("/{staff_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_staff_access(
    staff_user_id: uuid.UUID,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrAdmin,
) -> None:
    """Take this person's access to *this* gym away, leaving their account
    (and any role they hold at another gym) intact.

    A manager may only remove a coach — decision 25's shape again: a
    manager staffs the floor, and cannot remove a peer or the owner.
    """
    _user, role = await _staff_at_this_gym(session, staff_user_id)

    if claims.role == "manager" and role.role != "coach":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Managers can only remove coaches")

    await _guard_last_super_admin(session, role, becoming=None)

    await session.delete(role)
    await _revoke_refresh_tokens(session, staff_user_id)


class StaffPasswordOut(BaseModel):
    username: str
    password: str


@router.post("/{staff_user_id}/password/reset", response_model=StaffPasswordOut)
async def reset_password_for_staff(
    staff_user_id: uuid.UUID,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrAdmin,
) -> StaffPasswordOut:
    """Set a new password for someone at this gym and hand it back to the
    caller to deliver.

    Decision 26's shape rather than decision 20's: the password comes back
    in the response so a human sends it over a wa.me link, exactly as
    POST /staff already hands over a new coach's first password. No
    WhatsApp Business API call, so no per-message cost and no template.

    Deliberately does **not** write staff_users.password_reset_at. That
    column rate-limits the unauthenticated POST /auth/staff/password/reset,
    where anyone who knows a username can trigger a send; this endpoint is
    already gated by role. Setting it here would mean a manager helping a
    coach reset their password silently locks that coach out of the
    self-service flow for the cooldown.

    Revokes refresh tokens, because the reason to reset someone's password
    is almost always that the old one should stop working — which has to
    include the session already open on their phone.
    """
    user, role = await _staff_at_this_gym(session, staff_user_id)

    if claims.role == "manager" and role.role != "coach":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Managers can only reset a coach's password"
        )

    password = generate_password()
    user.password_hash = hash_secret(password)
    await _revoke_refresh_tokens(session, staff_user_id)
    return StaffPasswordOut(username=user.username, password=password)
