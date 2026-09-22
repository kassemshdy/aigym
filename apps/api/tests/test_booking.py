import itertools
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from urllib.parse import unquote

from httpx import AsyncClient

from app.db import tenant_session
from app.models import Attendance, Coach, GymClass, Member

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


async def _gym_and_staff_token(
    client: AsyncClient, *, slug: str
) -> tuple[uuid.UUID, dict[str, str]]:
    manager_username = f"mgr-{slug}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": manager_username,
            "manager_password": "hunter22", "manager_phone": f"+96179{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    gym_id = uuid.UUID(onboard.json()["gym_id"])

    login = await client.post(
        "/auth/staff/login", json={"username": manager_username, "password": "hunter22"}
    )
    assert login.status_code == 200, login.text
    return gym_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _member_token(
    client: AsyncClient, gym_id: uuid.UUID, staff_headers: dict[str, str], *, phone: str
) -> tuple[uuid.UUID, dict[str, str]]:
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Test Member",
                phone=phone, joined_at=datetime.now(UTC),
            )
        )

    code_response = await client.post(f"/auth/member/{member_id}/code", headers=staff_headers)
    wa_link = unquote(code_response.json()["wa_link"])
    code = re.search(r"code is (\d{6})", wa_link).group(1)  # type: ignore[union-attr]
    login = await client.post("/auth/member/login", json={"phone": phone, "code": code})
    assert login.status_code == 200, login.text
    return member_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _insert_coach(gym_id: uuid.UUID) -> uuid.UUID:
    coach_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Coach(
                id=coach_id, gym_id=gym_id,
                name={"ar": "كوتش", "en": "Coach"},
                speciality={"ar": "قوة", "en": "Strength"},
            )
        )
    return coach_id


async def _insert_class(gym_id: uuid.UUID, coach_id: uuid.UUID) -> uuid.UUID:
    class_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            GymClass(
                id=class_id, gym_id=gym_id,
                title={"ar": "كروسفت", "en": "CrossFit"},
                coach_id=coach_id, weekdays=[1, 3], time="18:00", duration_min=45,
            )
        )
    return class_id


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def test_list_coaches_and_classes(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="booking-a")
    coach_id = await _insert_coach(gym_id)
    await _insert_class(gym_id, coach_id)

    coaches = await client.get("/coaches", headers=staff_headers)
    assert coaches.status_code == 200
    assert any(c["id"] == str(coach_id) for c in coaches.json())

    classes = await client.get("/classes", headers=staff_headers)
    assert classes.status_code == 200
    assert len(classes.json()) == 1
    assert classes.json()[0]["weekdays"] == [1, 3]


async def test_member_can_create_list_and_cancel_own_booking(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="booking-b")
    coach_id = await _insert_coach(gym_id)
    _member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170800001"
    )

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    created = await client.post(
        "/members/me/bookings",
        headers=_idem(member_headers),
        json={"coach_id": str(coach_id), "date": tomorrow, "time": "18:00", "kind": "private"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "booked"
    booking_id = created.json()["id"]

    listed = await client.get("/members/me/bookings", headers=member_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    cancelled = await client.patch(
        f"/members/me/bookings/{booking_id}", headers=_idem(member_headers)
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_a_member_cannot_cancel_another_members_booking(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="booking-c")
    coach_id = await _insert_coach(gym_id)
    _a_id, a_headers = await _member_token(client, gym_id, staff_headers, phone="+96170800002")
    _b_id, b_headers = await _member_token(client, gym_id, staff_headers, phone="+96170800003")

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    created = await client.post(
        "/members/me/bookings",
        headers=_idem(a_headers),
        json={"coach_id": str(coach_id), "date": tomorrow, "time": "18:00", "kind": "private"},
    )
    booking_id = created.json()["id"]

    response = await client.patch(
        f"/members/me/bookings/{booking_id}", headers=_idem(b_headers)
    )
    assert response.status_code == 404

    b_listed = await client.get("/members/me/bookings", headers=b_headers)
    assert b_listed.json() == []


async def test_member_attendance_is_own_only(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="booking-d")
    a_id, a_headers = await _member_token(client, gym_id, staff_headers, phone="+96170800004")
    _b_id, b_headers = await _member_token(client, gym_id, staff_headers, phone="+96170800005")

    async with tenant_session(gym_id) as session:
        session.add(
            Attendance(id=uuid.uuid4(), gym_id=gym_id, member_id=a_id, date=date.today())
        )

    a_listed = await client.get("/members/me/attendance", headers=a_headers)
    assert len(a_listed.json()) == 1

    b_listed = await client.get("/members/me/attendance", headers=b_headers)
    assert b_listed.json() == []


async def test_member_cannot_read_another_members_workout_sessions(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="booking-e")
    a_id, _a_headers = await _member_token(client, gym_id, staff_headers, phone="+96170800006")
    _b_id, b_headers = await _member_token(client, gym_id, staff_headers, phone="+96170800007")

    response = await client.get(f"/members/{a_id}/workout-sessions", headers=b_headers)
    assert response.status_code == 404
