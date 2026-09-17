import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentSession, require_role
from app.models import StaffGymRole, StaffUser
from app.security.hashing import hash_secret
from app.security.jwt import AccessTokenClaims

router = APIRouter(prefix="/staff", tags=["staff"])

ManagerOrAdmin = Depends(require_role("super_admin", "manager"))


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
