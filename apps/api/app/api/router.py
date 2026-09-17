from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.checkins import router as checkins_router
from app.api.exercises import router as exercises_router
from app.api.machines import router as machines_router
from app.api.members import router as members_router
from app.api.nutrition import router as nutrition_router
from app.api.onboarding import router as onboarding_router
from app.api.payments import router as payments_router
from app.api.plans import router as plans_router
from app.api.programs import router as programs_router
from app.api.sessions import router as sessions_router
from app.api.staff import router as staff_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(onboarding_router)
api_router.include_router(checkins_router)
api_router.include_router(plans_router)
api_router.include_router(members_router)
api_router.include_router(payments_router)
api_router.include_router(staff_router)
api_router.include_router(exercises_router)
api_router.include_router(machines_router)
api_router.include_router(programs_router)
api_router.include_router(sessions_router)
api_router.include_router(nutrition_router)
