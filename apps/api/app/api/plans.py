"""Plan CRUD — the gym's own price list.

Until Phase 6 this was a read-only list, so a gym was stuck forever with
the $30/$80/$280 that app/api/onboarding.py hands every new tenant. That
is a pilot blocker rather than a nicety: the GTM guarantee is settled on
dues arithmetic, and dues come from a plan's price, so wrong prices make
the headline number wrong in the one report the gym is paying attention to.

**A price edit is retroactive, and that is worth knowing.** Nothing
snapshots what a membership period cost when it was sold — Subscription
carries a plan_id, and both compute_dues (app/domain/dues.py) and the
owner dashboard (app/api/analytics.py) resolve the price through it at
read time. So raising a plan from $30 to $40 also changes what last
quarter's collected and uncollected figures say, after the fact.

For dues that is arguably right: a member who never renewed owes today's
price for the renewal they still have not made. For the historical
analytics it is not — those periods really were worth $30. Fixing it
properly means snapshotting the price onto Subscription at creation, which
is its own change with its own migration and backfill, not something to
smuggle in here.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentSession, require_role
from app.models import Plan, Subscription
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["plans"])

ManagerOrAdmin = Depends(require_role("super_admin", "manager"))


class BilingualName(BaseModel):
    """Both languages required. Looser than the `dict[str, Any]` the
    exercise and video endpoints take, deliberately: those carry seeded
    content, while a gym owner types this one — and a plan saved with only
    English renders as a blank name on the Arabic side of the app rather
    than failing loudly."""

    ar: Annotated[str, Field(min_length=1, max_length=60)]
    en: Annotated[str, Field(min_length=1, max_length=60)]


class PlanOut(BaseModel):
    id: uuid.UUID
    name: dict[str, Any]
    price_usd: float
    days: int

    model_config = {"from_attributes": True}


class CreatePlanRequest(BaseModel):
    name: BilingualName
    #: Above zero: a free plan would make a member permanently "paid" with
    #: nothing owed, which silently removes them from every figure the
    #: guarantee is settled on rather than reading as a deliberate comp.
    price_usd: Annotated[float, Field(gt=0, le=100_000)]
    days: Annotated[int, Field(ge=1, le=3650)]


class UpdatePlanRequest(BaseModel):
    name: BilingualName | None = None
    price_usd: Annotated[float, Field(gt=0, le=100_000)] | None = None
    days: Annotated[int, Field(ge=1, le=3650)] | None = None


async def _plan_or_404(session: CurrentSession, plan_id: uuid.UUID) -> Plan:
    """RLS scopes plans to the caller's gym, so another gym's plan id is a
    404 here rather than a 403 — it does not exist as far as this gym is
    concerned, and saying otherwise would confirm it is real."""
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No plan with that id at this gym")
    return plan


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(session: CurrentSession) -> list[Plan]:
    result = await session.execute(select(Plan).order_by(Plan.price_usd))
    return list(result.scalars().all())


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: CreatePlanRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrAdmin,
) -> Plan:
    plan = Plan(
        id=uuid.uuid4(),
        gym_id=claims.gym_id,
        name=body.name.model_dump(),
        price_usd=body.price_usd,
        days=body.days,
    )
    session.add(plan)
    await session.flush()
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: uuid.UUID,
    body: UpdatePlanRequest,
    session: CurrentSession,
    _claims: AccessTokenClaims = ManagerOrAdmin,
) -> Plan:
    """See the module docstring on what a price change does to figures that
    have already been reported."""
    plan = await _plan_or_404(session, plan_id)
    if body.name is not None:
        plan.name = body.name.model_dump()
    if body.price_usd is not None:
        plan.price_usd = body.price_usd
    if body.days is not None:
        plan.days = body.days
    return plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: uuid.UUID,
    session: CurrentSession,
    _claims: AccessTokenClaims = ManagerOrAdmin,
) -> None:
    """A plan any membership period ever referenced cannot be deleted.

    subscriptions.plan_id is ON DELETE RESTRICT, so the database refuses
    this anyway — but it refuses with an IntegrityError at commit time,
    which reaches the client as a 500. The explicit count below turns that
    into a 409 that can say how many members are affected. The try/except
    still stands behind it for the narrow race where someone subscribes
    between the count and the flush.

    Deleting is not how a gym retires a plan, and should not be: the
    periods sold under it are what the dues and collection figures are
    made of. Stopping offering it is an editing decision, not a delete.
    """
    plan = await _plan_or_404(session, plan_id)

    in_use = (
        await session.execute(
            select(func.count()).select_from(Subscription).where(Subscription.plan_id == plan_id)
        )
    ).scalar_one()
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{in_use} membership periods use this plan",
        )

    await session.delete(plan)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Membership periods use this plan"
        ) from exc
