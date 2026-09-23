from fastapi import APIRouter

from app.api.ai_drafts import router as ai_drafts_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.booking import router as booking_router
from app.api.chat import router as chat_router
from app.api.checkins import router as checkins_router
from app.api.exercises import router as exercises_router
from app.api.food_entries import router as food_entries_router
from app.api.gyms import router as gyms_router
from app.api.machines import router as machines_router
from app.api.media import router as media_router
from app.api.member_import import router as member_import_router
from app.api.member_profile import router as member_profile_router
from app.api.members import router as members_router
from app.api.nutrition import router as nutrition_router
from app.api.onboarding import router as onboarding_router
from app.api.payments import router as payments_router
from app.api.plans import router as plans_router
from app.api.programs import router as programs_router
from app.api.progress_photos import router as progress_photos_router
from app.api.sessions import router as sessions_router
from app.api.staff import router as staff_router
from app.api.videos import router as videos_router

api_router = APIRouter()
api_router.include_router(ai_drafts_router)
api_router.include_router(analytics_router)
api_router.include_router(auth_router)
api_router.include_router(booking_router)
api_router.include_router(chat_router)
api_router.include_router(onboarding_router)
api_router.include_router(gyms_router)
api_router.include_router(checkins_router)
api_router.include_router(plans_router)
api_router.include_router(members_router)
api_router.include_router(member_import_router)
api_router.include_router(member_profile_router)
api_router.include_router(payments_router)
api_router.include_router(staff_router)
api_router.include_router(exercises_router)
api_router.include_router(machines_router)
api_router.include_router(media_router)
api_router.include_router(programs_router)
api_router.include_router(sessions_router)
api_router.include_router(nutrition_router)
api_router.include_router(videos_router)
api_router.include_router(food_entries_router)
api_router.include_router(progress_photos_router)
