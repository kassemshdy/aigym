"""Import every model module so it registers on Base.metadata.

Alembic's env.py imports this package before autogenerating; a model that
isn't imported here is invisible to `alembic revision --autogenerate`.
"""

from app.models.auth import MemberLoginCode, RefreshToken
from app.models.floor import Attendance, Booking, CheckIn, Coach, GymClass, Machine
from app.models.money import Payment, Plan, Subscription
from app.models.people import Member, MemberProfile
from app.models.plumbing import IdempotencyKey
from app.models.tenancy import Gym, StaffGymRole, StaffUser

__all__ = [
    "Attendance",
    "Booking",
    "CheckIn",
    "Coach",
    "Gym",
    "GymClass",
    "IdempotencyKey",
    "Machine",
    "Member",
    "MemberLoginCode",
    "MemberProfile",
    "Payment",
    "Plan",
    "RefreshToken",
    "StaffGymRole",
    "StaffUser",
    "Subscription",
]
