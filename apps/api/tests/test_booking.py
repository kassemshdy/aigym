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


# ---------------------------------------------------------------------
# Decision 50: a gym's bookable coaches are its coach accounts, and its
# classes are its own to set.
# ---------------------------------------------------------------------


async def _add_coach_account(
    client: AsyncClient, headers: dict[str, str], *, username: str, name: str
) -> str:
    created = await client.post(
        "/staff",
        headers=_idem(headers),
        json={
            "username": username, "password": "hunter22", "name": name,
            "phone": f"+96179{next(_counter):06d}", "role": "coach",
        },
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def test_a_coach_added_under_staff_is_bookable_and_leaves_with_their_access(
    client: AsyncClient,
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="booking-staff-coach")
    staff_id = await _add_coach_account(
        client, staff_headers, username="coach-rana", name="Rana"
    )
    _member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170800101"
    )

    listed = (await client.get("/coaches", headers=member_headers)).json()
    rana = [c for c in listed if c["name"]["en"] == "Rana"]
    assert len(rana) == 1, listed
    coach_id = rana[0]["id"]

    # A name corrected under Staff is corrected on the booking screen too.
    await client.patch(
        f"/staff/{staff_id}/details", headers=_idem(staff_headers), json={"name": "Rana K."}
    )
    renamed = (await client.get("/coaches", headers=member_headers)).json()
    assert [c["name"]["en"] for c in renamed if c["id"] == coach_id] == ["Rana K."]

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    booked = await client.post(
        "/members/me/bookings",
        headers=_idem(member_headers),
        json={"coach_id": coach_id, "date": tomorrow, "time": "18:00", "kind": "private"},
    )
    assert booked.status_code == 201, booked.text

    removed = await client.delete(f"/staff/{staff_id}", headers=_idem(staff_headers))
    assert removed.status_code == 204, removed.text

    after = (await client.get("/coaches", headers=member_headers)).json()
    assert coach_id not in {c["id"] for c in after}, "a removed coach can still be booked"
    # Their past booking survives: the profile is hidden, never deleted.
    mine = (await client.get("/members/me/bookings", headers=member_headers)).json()
    assert [b["coach_id"] for b in mine] == [coach_id]


async def test_promoting_someone_to_coach_makes_them_bookable_once(client: AsyncClient) -> None:
    _gym_id, admin_headers = await _gym_and_staff_token(client, slug="booking-promote")
    created = await client.post(
        "/staff",
        headers=_idem(admin_headers),
        json={
            "username": "desk-sami", "password": "hunter22", "name": "Sami",
            "phone": f"+96179{next(_counter):06d}", "role": "manager",
        },
    )
    staff_id = created.json()["id"]
    before = (await client.get("/coaches", headers=admin_headers)).json()
    assert "Sami" not in {c["name"]["en"] for c in before}, "a manager is not bookable"

    for role in ("coach", "manager", "coach"):
        changed = await client.patch(
            f"/staff/{staff_id}", headers=_idem(admin_headers), json={"role": role}
        )
        assert changed.status_code == 200, changed.text

    names = [c["name"]["en"] for c in (await client.get("/coaches", headers=admin_headers)).json()]
    assert names.count("Sami") == 1, names


async def test_a_manager_sets_the_class_schedule(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="booking-classes")
    coach_id = await _insert_coach(gym_id)

    created = await client.post(
        "/classes",
        headers=_idem(headers),
        json={
            "title": {"ar": "يوغا", "en": "Yoga"}, "coach_id": str(coach_id),
            "weekdays": [3, 1, 3], "time": "07:30", "duration_min": 45,
        },
    )
    assert created.status_code == 201, created.text
    class_id = created.json()["id"]
    assert created.json()["weekdays"] == [1, 3], "days are stored once, in order"

    moved = await client.patch(
        f"/classes/{class_id}", headers=_idem(headers), json={"time": "19:00"}
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["time"] == "19:00"
    assert moved.json()["title"]["en"] == "Yoga", "a partial edit kept the rest"

    gone = await client.delete(f"/classes/{class_id}", headers=_idem(headers))
    assert gone.status_code == 204, gone.text
    assert (await client.get("/classes", headers=headers)).json() == []


async def test_a_class_cannot_be_nonsense(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="booking-classes-bad")
    coach_id = str(await _insert_coach(gym_id))
    base = {
        "title": {"ar": "يوغا", "en": "Yoga"}, "coach_id": coach_id,
        "weekdays": [1], "time": "07:30", "duration_min": 45,
    }
    for bad in (
        {"time": "25:00"}, {"time": "7:30pm"}, {"weekdays": []}, {"weekdays": [7]},
        {"duration_min": 0}, {"title": {"ar": "", "en": "Yoga"}},
    ):
        response = await client.post("/classes", headers=_idem(headers), json={**base, **bad})
        assert response.status_code == 422, (bad, response.text)

    unknown = await client.post(
        "/classes", headers=_idem(headers), json={**base, "coach_id": str(uuid.uuid4())}
    )
    assert unknown.status_code == 404


async def test_only_managers_set_the_schedule(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="booking-classes-auth")
    coach_id = str(await _insert_coach(gym_id))
    _member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170800102"
    )
    payload = {
        "title": {"ar": "يوغا", "en": "Yoga"}, "coach_id": coach_id,
        "weekdays": [1], "time": "07:30", "duration_min": 45,
    }
    as_member = await client.post("/classes", headers=_idem(member_headers), json=payload)
    assert as_member.status_code == 403, as_member.text

    await _add_coach_account(client, staff_headers, username="coach-nour", name="Nour")
    login = await client.post(
        "/auth/staff/login", json={"username": "coach-nour", "password": "hunter22"}
    )
    coach_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    as_coach = await client.post("/classes", headers=_idem(coach_headers), json=payload)
    assert as_coach.status_code == 403, as_coach.text
