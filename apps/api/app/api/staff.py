import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentSession, require_role
from app.models import StaffGymRole, StaffUser
from app.security.hashing import hash_secret
from app.security.jwt import AccessTokenClaims

router = APIRouter(prefix="/staff", tags=["staff"])


class CreateStaffRequest(BaseModel):
    username: str
    password: str
    name: str
    phone: str
    role: str  # "manager" | "coach" | "super_admin"


class StaffOut(BaseModel):
    id: uuid.UUID
    username: str
    name: str
    role: str


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
async def create_staff(
    body: CreateStaffRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = Depends(require_role("super_admin")),
) -> StaffOut:
    """Decision 21: only a super_admin creates staff accounts — a manager
    or coach cannot. staff_users has no RLS (it's not gym-scoped, same as
    decision 16's other two exceptions), so the username-uniqueness check
    below is correctly global across every gym, not just this one.
    """
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
