"""Operator routes: creating a gym, and tracking what we charge it.

**Gated by a shared secret, never by a role.** app/api/onboarding.py's own
POST /gyms grants `super_admin` to every gym's *first* account, so
`super_admin` means "owner of this gym", not "runs the platform". Gating
billing on it would let a gym mark its own SaaS subscription paid. The
X-Onboarding-Secret header is the only thing here that distinguishes us
from a customer.

**No owner connection either.** `gyms` carries no RLS policy at all
(decision 16's first exception), so `tenant_session(None)` reads and
writes every gym's row perfectly well as the app role — see its docstring.
get_owner_sessionmaker stays at its single call site (decision 18).
"""

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db import tenant_session
from app.models import Gym, Plan, StaffGymRole, StaffUser
from app.security.hashing import hash_secret
from app.settings import get_settings

router = APIRouter(tags=["onboarding"])

#: What a gym's SaaS subscription can be. `trial` is where every new gym
#: starts, which is the pilot's whole shape (docs/GTM.md).
BILLING_STATUSES = ("trial", "active", "past_due", "cancelled")


def _require_operator(secret: str | None) -> None:
    settings = get_settings()
    if secret != settings.onboarding_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid onboarding secret")

STARTER_PLANS: list[tuple[dict[str, Any], int, int]] = [
    ({"ar": "اشتراك شهري", "en": "Monthly"}, 30, 30),
    ({"ar": "اشتراك ٣ أشهر", "en": "3 Months"}, 80, 90),
    ({"ar": "اشتراك سنوي", "en": "Yearly"}, 280, 365),
]


class OnboardGymRequest(BaseModel):
    name_ar: str
    name_en: str
    slug: str
    manager_name: str
    manager_username: str
    manager_password: str
    manager_phone: str


class OnboardGymResponse(BaseModel):
    gym_id: uuid.UUID
    slug: str
    #: Echoed back so whoever ran this can hand over a working login
    #: without going back to what they typed. The password is not here on
    #: purpose — they chose it.
    manager_username: str
    staff_user_id: uuid.UUID


@router.post("/gyms", response_model=OnboardGymResponse, status_code=status.HTTP_201_CREATED)
async def onboard_gym(
    body: OnboardGymRequest,
    x_onboarding_secret: Annotated[str | None, Header()] = None,
) -> OnboardGymResponse:
    """Create a gym, its first manager, and starter plans in one transaction.

    There is no staff JWT yet at this point — nothing has been created — so
    a shared secret header is the only gate. This is meant for the platform
    operator to run once per new gym customer, not a public signup form.
    """
    _require_operator(x_onboarding_secret)

    gym_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        # Both of these are unique constraints that would otherwise raise
        # an IntegrityError at commit — outside this handler, reaching the
        # operator as a 500 with nothing to act on. Checking first turns
        # each into a 409 that says which field collided.
        #
        # A race between the check and the insert still ends as a 500; that
        # is acceptable for a route one person runs by hand, once per gym,
        # and it is not worth a savepoint to paper over.
        taken_slug = (
            await session.execute(select(Gym.id).where(Gym.slug == body.slug))
        ).scalar_one_or_none()
        if taken_slug is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "That slug is already taken")

        taken_username = (
            await session.execute(
                select(StaffUser.id).where(StaffUser.username == body.manager_username)
            )
        ).scalar_one_or_none()
        if taken_username is not None:
            # staff_users has no RLS and usernames are unique platform-wide
            # (decision 16), so this correctly collides across every gym,
            # not only this one.
            raise HTTPException(status.HTTP_409_CONFLICT, "That username is already taken")

        # gyms carries no RLS policy at all, so this insert doesn't depend on
        # app.gym_id — but staff_gym_roles and plans below do, and their
        # WITH CHECK just requires gym_id = app.gym_id, which we set to this
        # gym's own freshly generated id. No elevated connection needed: the
        # app role can legitimately create a brand-new tenant this way.
        session.add(Gym(id=gym_id, name={"ar": body.name_ar, "en": body.name_en}, slug=body.slug))
        await session.flush()

        staff = StaffUser(
            id=uuid.uuid4(),
            username=body.manager_username,
            phone=body.manager_phone,
            name=body.manager_name,
            password_hash=hash_secret(body.manager_password),
        )
        session.add(staff)
        await session.flush()

        # The account created here is the gym's first — decision 21: it has
        # to be super_admin, or nobody could ever create a second one.
        session.add(StaffGymRole(gym_id=gym_id, staff_user_id=staff.id, role="super_admin"))
        for name, price, days in STARTER_PLANS:
            session.add(Plan(gym_id=gym_id, name=name, price_usd=price, days=days))

    return OnboardGymResponse(
        gym_id=gym_id,
        slug=body.slug,
        manager_username=body.manager_username,
        staff_user_id=staff.id,
    )


# ---------------------------------------------------------------------
# Billing. Tracked, never processed — decision 3's open question stays
# open because Stripe does not serve Lebanese businesses. Money changes
# hands out of band; these routes record what was agreed and what has
# been paid, so "which gyms are past due" is answerable without a
# spreadsheet living somewhere else.
# ---------------------------------------------------------------------


class GymBillingOut(BaseModel):
    """Operator-only. Nothing that selects these fields may ever be
    reachable with a staff token — tests/test_billing.py walks the OpenAPI
    schema to keep that true."""

    gym_id: uuid.UUID
    slug: str
    name: dict[str, Any]
    billing_status: str
    monthly_usd: float | None
    paid_through: date | None
    billing_notes: str | None


def _billing_out(gym: Gym) -> GymBillingOut:
    return GymBillingOut(
        gym_id=gym.id,
        slug=gym.slug,
        name=gym.name,
        billing_status=gym.billing_status,
        monthly_usd=float(gym.monthly_usd) if gym.monthly_usd is not None else None,
        paid_through=gym.paid_through,
        billing_notes=gym.billing_notes,
    )


@router.get("/gyms", response_model=list[GymBillingOut])
async def list_gyms(
    x_onboarding_secret: Annotated[str | None, Header()] = None,
) -> list[GymBillingOut]:
    """Every gym on the platform and what it owes.

    At three to five pilot gyms this is the whole admin surface, which is
    why there is no cross-gym UI to go with it (the plan keeps platform
    administration to a script on purpose)."""
    _require_operator(x_onboarding_secret)
    async with tenant_session(None) as session:
        gyms = (await session.execute(select(Gym).order_by(Gym.slug))).scalars().all()
        return [_billing_out(g) for g in gyms]


@router.get("/gyms/{gym_id}/billing", response_model=GymBillingOut)
async def get_gym_billing(
    gym_id: uuid.UUID,
    x_onboarding_secret: Annotated[str | None, Header()] = None,
) -> GymBillingOut:
    _require_operator(x_onboarding_secret)
    async with tenant_session(None) as session:
        gym = await session.get(Gym, gym_id)
        if gym is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No gym with that id")
        return _billing_out(gym)


class UpdateBillingRequest(BaseModel):
    billing_status: Literal["trial", "active", "past_due", "cancelled"] | None = None
    monthly_usd: Annotated[float, Field(ge=0, le=100_000)] | None = None
    paid_through: date | None = None
    billing_notes: str | None = None


@router.patch("/gyms/{gym_id}/billing", response_model=GymBillingOut)
async def update_gym_billing(
    gym_id: uuid.UUID,
    body: UpdateBillingRequest,
    x_onboarding_secret: Annotated[str | None, Header()] = None,
) -> GymBillingOut:
    """Every field is clearable by sending an explicit null, which is why
    this reads model_fields_set rather than treating None as "not
    provided" — a gym that cancels needs paid_through taken off, and
    monthly_usd can go back to unknown."""
    _require_operator(x_onboarding_secret)
    async with tenant_session(None) as session:
        gym = await session.get(Gym, gym_id)
        if gym is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No gym with that id")

        if body.billing_status is not None:
            gym.billing_status = body.billing_status
        for nullable in ("monthly_usd", "paid_through", "billing_notes"):
            if nullable in body.model_fields_set:
                setattr(gym, nullable, getattr(body, nullable))

        await session.flush()
        return _billing_out(gym)
