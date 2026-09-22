"""Import every model module so it registers on Base.metadata.

Alembic's env.py imports this package before autogenerating; a model that
isn't imported here is invisible to `alembic revision --autogenerate`.
"""

from app.models.ai import AiPlanDraft
from app.models.auth import MemberLoginCode, RefreshToken
from app.models.content import FoodEntry, ProgressPhoto, Video
from app.models.floor import Attendance, Booking, CheckIn, Coach, GymClass, Machine
from app.models.money import Payment, Plan, Subscription
from app.models.people import Member, MemberProfile
from app.models.plumbing import IdempotencyKey
from app.models.tenancy import Gym, StaffGymRole, StaffUser
from app.models.training import (
    Exercise,
    MemberProgram,
    NutritionLog,
    ProgramExercise,
    WorkoutSession,
    WorkoutSet,
)

__all__ = [
    "AiPlanDraft",
    "Attendance",
    "Booking",
    "CheckIn",
    "Coach",
    "Exercise",
    "FoodEntry",
    "Gym",
    "GymClass",
    "IdempotencyKey",
    "Machine",
    "Member",
    "MemberLoginCode",
    "MemberProfile",
    "MemberProgram",
    "NutritionLog",
    "Payment",
    "Plan",
    "ProgramExercise",
    "ProgressPhoto",
    "RefreshToken",
    "StaffGymRole",
    "StaffUser",
    "Subscription",
    "Video",
    "WorkoutSession",
    "WorkoutSet",
]
