import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.db import tenant_session
from app.models import Gym, Plan, StaffGymRole, StaffUser
from app.security.hashing import hash_secret
from app.settings import get_settings

router = APIRouter(tags=["onboarding"])

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
    settings = get_settings()
    if x_onboarding_secret != settings.onboarding_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid onboarding secret")

    gym_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
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

    return OnboardGymResponse(gym_id=gym_id, slug=body.slug)
