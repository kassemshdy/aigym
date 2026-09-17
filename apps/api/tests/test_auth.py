import re
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote

from httpx import AsyncClient

from app.db import tenant_session
from app.models import Member
from app.settings import get_settings

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"  # matches Settings default


async def _onboard_gym(client: AsyncClient, *, slug: str = "test-gym") -> dict[str, str]:
    response = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي تجريبي",
            "name_en": "Test Gym",
            "slug": slug,
            "manager_name": "Manager Mona",
            "manager_username": "mona",
            "manager_password": "hunter22",
            "manager_phone": "+96170000001",
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, str] = response.json()
    return body


async def _insert_member(gym_id: uuid.UUID, *, phone: str) -> uuid.UUID:
    """There's no members endpoint yet (that's stage 5) — insert one
    directly so auth tests can isolate the auth flow under test."""
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Test Member",
                phone=phone, joined_at=datetime.now(UTC),
            )
        )
    return member_id


async def test_onboard_gym_requires_secret(client: AsyncClient) -> None:
    response = await client.post(
        "/gyms",
        json={
            "name_ar": "x", "name_en": "x", "slug": "no-secret",
            "manager_name": "x", "manager_username": "x",
            "manager_password": "hunter22", "manager_phone": "+9610",
        },
    )
    assert response.status_code == 401


async def test_onboard_and_staff_login(client: AsyncClient) -> None:
    onboarded = await _onboard_gym(client)

    login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    principal = me.json()
    assert principal["gym_id"] == onboarded["gym_id"]
    assert principal["subject_type"] == "staff"
    # The account POST /gyms creates has to be super_admin (decision 21) —
    # it's the only way a gym ever gets a second staff account.
    assert principal["role"] == "super_admin"


async def test_staff_login_wrong_password_rejected(client: AsyncClient) -> None:
    await _onboard_gym(client)
    response = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "wrong"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_and_revokes_old_token(client: AsyncClient) -> None:
    await _onboard_gym(client)
    login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    old_refresh = login.json()["refresh_token"]

    first_refresh = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert first_refresh.status_code == 200
    new_tokens = first_refresh.json()
    assert new_tokens["refresh_token"] != old_refresh

    # Reusing the same (now-rotated) refresh token must fail.
    reuse = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401

    # The freshly rotated token still works.
    second_refresh = await client.post(
        "/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert second_refresh.status_code == 200


async def test_member_code_login_flow(client: AsyncClient) -> None:
    await _onboard_gym(client)
    staff_login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    auth_header = {"Authorization": f"Bearer {staff_login.json()['access_token']}"}

    me = await client.get("/auth/me", headers=auth_header)
    gym_id = uuid.UUID(me.json()["gym_id"])
    member_id = await _insert_member(gym_id, phone="+96171111111")

    code_response = await client.post(f"/auth/member/{member_id}/code", headers=auth_header)
    assert code_response.status_code == 200, code_response.text
    wa_link = unquote(code_response.json()["wa_link"])
    match = re.search(r"code is (\d{6})", wa_link)
    assert match, wa_link
    code = match.group(1)

    login = await client.post(
        "/auth/member/login", json={"phone": "+96171111111", "code": code}
    )
    assert login.status_code == 200, login.text
    member_tokens = login.json()

    me_member = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {member_tokens['access_token']}"}
    )
    assert me_member.json()["subject_type"] == "member"

    # A code is single-use: the same code must not work twice.
    replay = await client.post(
        "/auth/member/login", json={"phone": "+96171111111", "code": code}
    )
    assert replay.status_code == 401


async def test_member_code_rate_limited(client: AsyncClient) -> None:
    await _onboard_gym(client)
    staff_login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    auth_header = {"Authorization": f"Bearer {staff_login.json()['access_token']}"}
    me = await client.get("/auth/me", headers=auth_header)
    gym_id = uuid.UUID(me.json()["gym_id"])
    member_id = await _insert_member(gym_id, phone="+96172222222")

    limit = get_settings().member_code_rate_limit_per_hour
    for _ in range(limit):
        response = await client.post(f"/auth/member/{member_id}/code", headers=auth_header)
        assert response.status_code == 200

    over_limit = await client.post(f"/auth/member/{member_id}/code", headers=auth_header)
    assert over_limit.status_code == 429


async def test_staff_password_reset_unknown_username(client: AsyncClient) -> None:
    response = await client.post("/auth/staff/password/reset", json={"username": "nobody"})
    assert response.status_code == 404


async def test_staff_password_reset_flow(client: AsyncClient, monkeypatch) -> None:
    await _onboard_gym(client)

    sent_to: list[str] = []

    async def fake_send(*, to: str, body: str) -> bool:
        sent_to.append(to)
        return True

    monkeypatch.setattr("app.api.auth.send_whatsapp_text", fake_send)

    reset = await client.post("/auth/staff/password/reset", json={"username": "mona"})
    assert reset.status_code == 200
    assert reset.json() == {"sent": True}
    # Delivered to the phone on file, even though the lookup was by username.
    assert sent_to == ["+96170000001"]

    # The old password (set at onboarding) no longer works.
    old_password_login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    assert old_password_login.status_code == 401

    # Immediately resetting again is rate-limited.
    again = await client.post("/auth/staff/password/reset", json={"username": "mona"})
    assert again.status_code == 429


async def test_staff_password_reset_without_whatsapp_configured(client: AsyncClient) -> None:
    """No monkeypatch here — exercises the real send_whatsapp_text, which
    returns False without ever making a network call when the Settings
    default (both WhatsApp variables unset) is in effect."""
    await _onboard_gym(client)
    response = await client.post("/auth/staff/password/reset", json={"username": "mona"})
    assert response.status_code == 200
    assert response.json() == {"sent": False}


async def test_only_super_admin_can_create_staff(client: AsyncClient) -> None:
    await _onboard_gym(client)
    super_admin_login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    admin_header = {"Authorization": f"Bearer {super_admin_login.json()['access_token']}"}

    create = await client.post(
        "/staff",
        headers={**admin_header, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "username": "karim",
            "password": "coachpass1",
            "name": "Karim",
            "phone": "+96170000002",
            "role": "coach",
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["role"] == "coach"

    coach_login = await client.post(
        "/auth/staff/login", json={"username": "karim", "password": "coachpass1"}
    )
    assert coach_login.status_code == 200
    coach_header = {"Authorization": f"Bearer {coach_login.json()['access_token']}"}

    # A coach cannot create another staff account.
    forbidden = await client.post(
        "/staff",
        headers={**coach_header, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "username": "abed",
            "password": "coachpass2",
            "name": "Abed",
            "phone": "+96170000003",
            "role": "coach",
        },
    )
    assert forbidden.status_code == 403


async def test_manager_can_create_coach_but_not_manager_or_super_admin(
    client: AsyncClient,
) -> None:
    await _onboard_gym(client)
    admin_login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    admin_header = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # super_admin creates a manager, so there's a manager account to test with.
    create_manager = await client.post(
        "/staff",
        headers={**admin_header, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "username": "nour",
            "password": "managerpass1",
            "name": "Nour",
            "phone": "+96170000010",
            "role": "manager",
        },
    )
    assert create_manager.status_code == 201, create_manager.text

    manager_login = await client.post(
        "/auth/staff/login", json={"username": "nour", "password": "managerpass1"}
    )
    manager_header = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}

    # A manager can create a coach.
    create_coach = await client.post(
        "/staff",
        headers={**manager_header, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "username": "karim2",
            "password": "coachpass1",
            "name": "Karim",
            "phone": "+96170000011",
            "role": "coach",
        },
    )
    assert create_coach.status_code == 201, create_coach.text
    assert create_coach.json()["role"] == "coach"

    # A manager cannot create another manager...
    forbidden_manager = await client.post(
        "/staff",
        headers={**manager_header, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "username": "rita",
            "password": "managerpass2",
            "name": "Rita",
            "phone": "+96170000012",
            "role": "manager",
        },
    )
    assert forbidden_manager.status_code == 403

    # ...or a super_admin.
    forbidden_admin = await client.post(
        "/staff",
        headers={**manager_header, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "username": "sami",
            "password": "adminpass1",
            "name": "Sami",
            "phone": "+96170000013",
            "role": "super_admin",
        },
    )
    assert forbidden_admin.status_code == 403


async def test_list_staff_shows_everyone_at_the_gym(client: AsyncClient) -> None:
    await _onboard_gym(client)
    admin_login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    admin_header = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    await client.post(
        "/staff",
        headers={**admin_header, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "username": "abed2",
            "password": "coachpass3",
            "name": "Abed",
            "phone": "+96170000020",
            "role": "coach",
        },
    )

    listing = await client.get("/staff", headers=admin_header)
    assert listing.status_code == 200
    usernames = {row["username"] for row in listing.json()}
    assert {"mona", "abed2"} <= usernames


async def test_create_staff_rejects_duplicate_username(client: AsyncClient) -> None:
    await _onboard_gym(client)
    login = await client.post(
        "/auth/staff/login", json={"username": "mona", "password": "hunter22"}
    )
    admin_header = {"Authorization": f"Bearer {login.json()['access_token']}"}

    duplicate = await client.post(
        "/staff",
        headers={**admin_header, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "username": "mona",
            "password": "whatever1",
            "name": "Someone Else",
            "phone": "+96170000004",
            "role": "coach",
        },
    )
    assert duplicate.status_code == 409
