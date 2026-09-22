"""The gym's own identity: its name and its logo.

**Branding only. Never billing.** Stage 12 puts the gym's SaaS
subscription state (status, monthly_usd, paid_through) on this same table,
and the boundary between "the gym's data" and "what we charge the gym" is
enforced here by what GymOut selects — not by RLS, which `gyms` does not
have, and not by a role, since the gym owner is a super_admin *of their own
gym* (app/api/onboarding.py grants it to every first account) and would
happily pass any role check on their own billing row.
tests/test_gyms.py pins the response's exact key set so widening this model
later is a failing test rather than a quiet leak.

**`gyms` carries no Row-Level Security** — decision 16's first deliberate
exception, because a gym does not scope itself and onboarding has to write
this table before any `app.gym_id` exists. Everything below therefore
filters on `claims.gym_id` by hand. That is the one place in this codebase
where forgetting a WHERE clause is a cross-tenant bug rather than a no-op,
which is why there is only one query and it is a primary-key lookup.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app import storage
from app.api.schemas import BilingualName
from app.deps import CurrentClaims, CurrentSession, require_role
from app.models import Gym
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["gyms"])

ManagerOrAdmin = Depends(require_role("super_admin", "manager"))


class GymOut(BaseModel):
    id: uuid.UUID
    name: dict[str, Any]
    slug: str
    #: None until the gym uploads one; the client falls back to the
    #: bundled logo rather than showing a gap.
    logo_key: str | None

    model_config = {"from_attributes": True}


class UpdateGymRequest(BaseModel):
    name: BilingualName | None = None
    #: Explicit null clears the logo. Unlike the other PATCH endpoints in
    #: this service, which treat None as "not provided", this one reads
    #: model_fields_set — otherwise a gym could set a logo and never
    #: remove it.
    logo_key: str | None = None


async def _own_gym(session: CurrentSession, claims: AccessTokenClaims) -> Gym:
    gym = await session.get(Gym, claims.gym_id)
    if gym is None:
        # A live token naming a gym that no longer exists. Not reachable
        # in normal operation, but returning None-shaped nonsense to the
        # client would be worse than saying so.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")
    return gym


@router.get("/gyms/me", response_model=GymOut)
async def get_own_gym(session: CurrentSession, claims: CurrentClaims) -> Gym:
    """Readable by anyone signed in, members included: the gym's name and
    logo are in the app's header on every surface, not just the manager's."""
    return await _own_gym(session, claims)


@router.patch("/gyms/me", response_model=GymOut)
async def update_own_gym(
    body: UpdateGymRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrAdmin,
) -> Gym:
    gym = await _own_gym(session, claims)

    if body.name is not None:
        gym.name = body.name.model_dump()

    if "logo_key" in body.model_fields_set:
        if body.logo_key is not None:
            # A key that is malformed or names nothing on disk would render
            # as a broken image in the header of every screen, on every
            # surface, with nothing to say what went wrong.
            try:
                exists = storage.exists(body.logo_key)
            except storage.InvalidKey as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a valid media key"
                ) from exc
            if not exists:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, "No uploaded file with that key"
                )
        gym.logo_key = body.logo_key

    await session.flush()
    return gym
