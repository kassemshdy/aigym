"""Seed the database with Triple A Gym's real content.

Mirrors apps/web/src/mocks/data.ts exactly — same members, plans, coaches,
machines and class schedule — so a manager screen looks identical the
moment it switches from mocks to the API (stage 6). Connects with the
migrations role (the table owner), since it must bypass RLS to write rows
for a gym before any request has set app.gym_id.

Idempotent: safe to re-run against an already-seeded database — it deletes
and re-inserts by fixed id, matching the mock data's own fixed ids.

Runs automatically on every `api` deploy in production, as the service's
Railway Pre-Deploy Command — that's exactly what idempotency is for here:
it costs nothing on a deploy where nothing changed, and it's what lets a
future edit to the seed data (a new class time, a corrected plan price)
ship the same way as any other code change, rather than needing a manual
`railway ssh` run after every merge. See docs/DEPLOY.md.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    Attendance,
    Booking,
    CheckIn,
    Coach,
    Gym,
    GymClass,
    Machine,
    Member,
    MemberProfile,
    Payment,
    Plan,
    StaffGymRole,
    StaffUser,
    Subscription,
)
from app.settings import get_settings

GYM_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Deterministic ids (uuid5 off the mock's own string ids) so re-seeding never
# duplicates a row and foreign keys below can just reference these directly.
NAMESPACE = uuid.UUID("6f2a9e3e-2f3e-4a8b-9e7a-6a2b9b6f1a11")


def uid(kind: str, mock_id: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{mock_id}")


def d(iso_date: str) -> datetime:
    return datetime.fromisoformat(iso_date).replace(tzinfo=UTC)


def iso_days_from_today(delta: int) -> date:
    return date.today() + timedelta(days=delta)


PLAN_ROWS = [
    ("p1", {"ar": "اشتراك شهري", "en": "Monthly"}, 35, 30),
    ("p3", {"ar": "اشتراك ٣ أشهر", "en": "3 Months"}, 90, 90),
    ("p12", {"ar": "اشتراك سنوي", "en": "Yearly"}, 300, 365),
    ("pt", {"ar": "تدريب خاص", "en": "Personal Training"}, 150, 30),
]

class MemberSeed(NamedTuple):
    mock_id: str
    name: str
    name_en: str
    phone: str
    plan_mock_id: str
    joined_at: str
    ends_at: str
    goal: str
    level: str
    height_cm: int
    weight_kg: int
    body_fat: int
    injuries: list[dict[str, str]]
    days_per_week: int
    job: str
    sleep_hours: int
    weight_trend: list[int]


MEMBER_ROWS = [
    MemberSeed(
        "m0", "قاسم شحادي", "Kassem Shehady", "+96170622211", "pt",
        "2026-03-02", "2026-10-02", "strength", "mid", 177, 80, 19, [],
        3, "desk", 7, [84, 83, 83, 82, 81, 81, 80],
    ),
    MemberSeed(
        "m1", "رامي حداد", "Rami Haddad", "+96170123456", "p1",
        "2025-11-02", "2026-09-08", "lose", "mid", 178, 92, 26,
        [{"ar": "أسفل الظهر", "en": "Lower back"}],
        3, "desk", 6, [98, 97, 96, 95, 94, 93, 92],
    ),
    MemberSeed(
        "m2", "نور عبدالله", "Nour Abdallah", "+96176334521", "p3",
        "2026-06-14", "2026-09-14", "strength", "strong", 165, 61, 21, [],
        5, "active", 8, [58, 58, 59, 59, 60, 60, 61],
    ),
    MemberSeed(
        "m3", "جاد خوري", "Jad Khoury", "+96171889012", "p12",
        "2026-01-08", "2027-01-08", "gain", "mid", 182, 74, 14, [],
        4, "desk", 7, [70, 70, 71, 72, 72, 73, 74],
    ),
    MemberSeed(
        "m4", "مايا شمعون", "Maya Chamoun", "+96103445566", "p1",
        "2026-08-01", "2026-09-01", "health", "new", 170, 68, 29,
        [{"ar": "ركبة يمين", "en": "Right knee"}],
        2, "shift", 5, [69, 69, 69, 68, 68, 68, 68],
    ),
    MemberSeed(
        "m5", "علي حمدان", "Ali Hamdan", "+96181220034", "pt",
        "2026-05-20", "2026-09-20", "strength", "strong", 175, 84, 16,
        [{"ar": "كتف يسار", "en": "Left shoulder"}],
        5, "active", 7, [82, 82, 83, 83, 83, 84, 84],
    ),
    MemberSeed(
        "m6", "سيرين نصار", "Sirine Nassar", "+96170998877", "p3",
        "2026-07-05", "2026-10-05", "lose", "new", 162, 71, 31, [],
        3, "desk", 6, [75, 74, 74, 73, 72, 72, 71],
    ),
    MemberSeed(
        "m7", "طوني عون", "Tony Aoun", "+96176112233", "p1",
        "2026-04-11", "2026-09-11", "gain", "mid", 180, 79, 18, [],
        4, "shift", 6, [76, 76, 77, 77, 78, 79, 79],
    ),
    MemberSeed(
        "m8", "ليلى مراد", "Layla Mrad", "+96171445599", "p1",
        "2026-02-19", "2026-08-19", "health", "mid", 168, 64, 24, [],
        2, "desk", 7, [66, 66, 65, 65, 65, 64, 64],
    ),
]

PAYMENT_ROWS = [
    ("y1", "m3", 300, "2026-01-08", "cash"),
    ("y2", "m6", 90, "2026-07-05", "cash"),
    ("y3", "m5", 150, "2026-08-20", "transfer"),
    ("y4", "m2", 90, "2026-06-14", "cash"),
    ("y5", "m7", 35, "2026-08-11", "cash"),
]

COACH_ROWS = [
    (
        "c-assaf",
        {"ar": "الكوتش عساف", "en": "Coach Assaf"},
        {"ar": "قوة وتقنية الرفع", "en": "Strength and lifting technique"},
    ),
    (
        "c-karim",
        {"ar": "الكوتش كريم", "en": "Coach Karim"},
        {"ar": "تنحيف وكارديو", "en": "Fat loss and conditioning"},
    ),
    (
        "c-abed",
        {"ar": "الكوتش عبد", "en": "Coach Abed"},
        {"ar": "كمال أجسام وتضخيم", "en": "Bodybuilding and hypertrophy"},
    ),
]

MACHINE_ROWS = [
    ("mc-bench", {"ar": "بنش", "en": "Bench"}, "free-weights"),
    ("mc-incline", {"ar": "بنش مائل", "en": "Incline bench"}, "free-weights"),
    ("mc-rack", {"ar": "قفص السكوات", "en": "Squat rack"}, "free-weights"),
    ("mc-barbell", {"ar": "بار حر", "en": "Barbell"}, "free-weights"),
    ("mc-dumbbell", {"ar": "دمبل", "en": "Dumbbells"}, "free-weights"),
    ("mc-cable", {"ar": "جهاز الكابل", "en": "Cable tower"}, "machines"),
    ("mc-legpress", {"ar": "ضغط أرجل", "en": "Leg press"}, "machines"),
    ("mc-assist", {"ar": "جهاز العقلة المساعد", "en": "Assisted pull-up"}, "machines"),
    ("mc-tread", {"ar": "مشاية", "en": "Treadmill"}, "cardio"),
    ("mc-bike", {"ar": "بسكليت", "en": "Bike"}, "cardio"),
    ("mc-floor", {"ar": "أرض التمرين", "en": "Floor"}, "floor"),
]

CLASS_ROWS = [
    ("cl-cardio", {"ar": "كارديو وبطن", "en": "Cardio & Abs"}, "c-karim", [2, 5], "19:00", 45),
    (
        "cl-strength",
        {"ar": "قوة للمبتدئين", "en": "Strength Basics"},
        "c-assaf",
        [1, 3],
        "18:00",
        60,
    ),
    ("cl-hyper", {"ar": "تضخيم", "en": "Hypertrophy"}, "c-abed", [0, 4], "20:00", 60),
]

BOOKING_ROWS = [
    ("b1", "m0", "c-abed", 1, "18:00", "private"),
    ("b2", "m0", "c-karim", 4, "19:00", "private"),
    ("b3", "m4", "c-karim", 2, "17:00", "intro"),
]

CHECKIN_ROWS = [
    ("c1", "m3", "17:05", "waiting"),
    ("c2", "m1", "17:12", "waiting"),
    ("c3", "m5", "17:20", "training"),
    ("c4", "m2", "16:40", "done"),
    ("c5", "m6", "16:15", "done"),
]

# member -> (weekday set, days-ago the pattern stops) — mirrors data.ts exactly,
# including the deliberately lapsed members for the "stopped coming" list.
ATTENDANCE_PATTERN: dict[str, tuple[list[int], int]] = {
    "m0": ([0, 2, 4], 0),
    "m1": ([1, 4], 2),
    "m2": ([0, 2, 3, 5], 1),
    "m3": ([1, 3, 5], 0),
    "m4": ([2], 23),
    "m5": ([0, 1, 3, 4], 1),
    "m6": ([2, 5], 4),
    "m7": ([1, 4], 12),
    "m8": ([3], 31),
}


async def seed(session: AsyncSession) -> None:
    # Deleting the gym cascades to everything gym-scoped, including this
    # seed's own staff_gym_roles row — but staff_users itself is NOT
    # gym-scoped (decision: a staff account can hold roles at more than one
    # gym) and is never deleted here. It carries a real, human-chosen
    # pin_hash once scripts/set_staff_pin.py has run; re-seeding must never
    # touch that, or every future deploy (this runs as the api service's
    # Pre-Deploy Command) would silently log the manager out.
    await session.execute(delete(Gym).where(Gym.id == GYM_ID))
    await session.flush()

    session.add(
        Gym(
            id=GYM_ID,
            name={"ar": "نادي تريبل إي — عرمون", "en": "Triple A Gym — Aaramoun"},
            slug="triple-a",
        )
    )
    # No relationship() is declared anywhere in app/models — these are plain
    # FK columns — so the unit of work has no dependency graph to order
    # inserts across tables by itself. Flush at each parent/child boundary
    # instead of relying on it to infer gyms-before-members-before-attendance.
    await session.flush()

    plan_ids: dict[str, uuid.UUID] = {}
    for mock_id, name, price, days in PLAN_ROWS:
        pid = uid("plan", mock_id)
        plan_ids[mock_id] = pid
        session.add(Plan(id=pid, gym_id=GYM_ID, name=name, price_usd=price, days=days))

    coach_ids: dict[str, uuid.UUID] = {}
    for mock_id, name, speciality in COACH_ROWS:
        cid = uid("coach", mock_id)
        coach_ids[mock_id] = cid
        session.add(Coach(id=cid, gym_id=GYM_ID, name=name, speciality=speciality))

    for mock_id, name, area in MACHINE_ROWS:
        session.add(Machine(id=uid("machine", mock_id), gym_id=GYM_ID, name=name, area=area))

    await session.flush()  # classes.coach_id references the coaches just added above

    for mock_id, title, coach_mock_id, weekdays, time, duration in CLASS_ROWS:
        session.add(
            GymClass(
                id=uid("class", mock_id),
                gym_id=GYM_ID,
                title=title,
                coach_id=coach_ids[coach_mock_id],
                weekdays=weekdays,
                time=time,
                duration_min=duration,
            )
        )

    member_ids: dict[str, uuid.UUID] = {}
    for m in MEMBER_ROWS:
        mid = uid("member", m.mock_id)
        member_ids[m.mock_id] = mid
        session.add(
            Member(
                id=mid, gym_id=GYM_ID, name=m.name, name_en=m.name_en, phone=m.phone,
                joined_at=d(m.joined_at),
            )
        )
        session.add(
            MemberProfile(
                member_id=mid, gym_id=GYM_ID, goal=m.goal, level=m.level,
                height_cm=m.height_cm, weight_kg=m.weight_kg, body_fat=m.body_fat,
                injuries=m.injuries, days_per_week=m.days_per_week, job=m.job,
                sleep_hours=m.sleep_hours, weight_trend=m.weight_trend,
            )
        )

    await session.flush()  # subscriptions below reference the members just added

    for m in MEMBER_ROWS:
        session.add(
            Subscription(
                id=uid("subscription", m.mock_id),
                gym_id=GYM_ID,
                member_id=member_ids[m.mock_id],
                plan_id=plan_ids[m.plan_mock_id],
                starts_at=d(m.joined_at),
                ends_at=d(m.ends_at),
            )
        )

    await session.flush()  # payments/check-ins/bookings/attendance reference members above

    for mock_id, member_mock_id, amount, at, method in PAYMENT_ROWS:
        session.add(
            Payment(
                id=uid("payment", mock_id), gym_id=GYM_ID, member_id=member_ids[member_mock_id],
                amount_usd=amount, at=d(at), method=method,
            )
        )

    for mock_id, member_mock_id, at, status in CHECKIN_ROWS:
        hh, mm = (int(part) for part in at.split(":"))
        today = datetime.now(UTC).replace(hour=hh, minute=mm, second=0, microsecond=0)
        session.add(
            CheckIn(
                id=uid("checkin", mock_id), gym_id=GYM_ID, member_id=member_ids[member_mock_id],
                at=today, status=status,
            )
        )

    for mock_id, member_mock_id, coach_mock_id, days_out, time, kind in BOOKING_ROWS:
        session.add(
            Booking(
                id=uid("booking", mock_id), gym_id=GYM_ID, member_id=member_ids[member_mock_id],
                coach_id=coach_ids[coach_mock_id], date=iso_days_from_today(days_out),
                time=time, kind=kind, status="booked",
            )
        )

    for member_mock_id, (weekdays, until) in ATTENDANCE_PATTERN.items():
        for back in range(until, 56):
            day = date.today() - timedelta(days=back)
            # Python's date.weekday() is Monday=0; data.ts's pattern keys are
            # Date.getDay() where Sunday=0. Convert so the same 'days' list
            # picks the same weekdays.
            js_weekday = (day.weekday() + 1) % 7
            if js_weekday in weekdays:
                session.add(
                    Attendance(
                        id=uuid.uuid5(NAMESPACE, f"attendance:{member_mock_id}:{day.isoformat()}"),
                        gym_id=GYM_ID,
                        member_id=member_ids[member_mock_id],
                        date=day,
                    )
                )

    staff_id = uid("staff", "kassem")
    staff = await session.get(StaffUser, staff_id)
    if staff is None:
        staff = StaffUser(
            id=staff_id, phone="+96170622211", name="Kassem Shehady", pin_hash=None
        )
        session.add(staff)
        await session.flush()  # staff_gym_roles.staff_user_id references staff just added above
    session.add(
        StaffGymRole(
            id=uid("role", "kassem-manager"), gym_id=GYM_ID, staff_user_id=staff.id, role="manager"
        )
    )

    await session.commit()


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url_migrations)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        await seed(session)
    await engine.dispose()
    print(f"Seeded gym {GYM_ID} (Triple A Gym — Aaramoun)")


if __name__ == "__main__":
    asyncio.run(main())
