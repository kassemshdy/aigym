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
            "manager_phone": "+96170000001",
            "manager_pin": "1234",
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
            "manager_name": "x", "manager_phone": "+9610", "manager_pin": "1234",
        },
    )
    assert response.status_code == 401


async def test_onboard_and_staff_login(client: AsyncClient) -> None:
    onboarded = await _onboard_gym(client)

    login = await client.post(
        "/auth/staff/login", json={"phone": "+96170000001", "pin": "1234"}
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
    assert principal["role"] == "manager"


async def test_staff_login_wrong_pin_rejected(client: AsyncClient) -> None:
    await _onboard_gym(client)
    response = await client.post(
        "/auth/staff/login", json={"phone": "+96170000001", "pin": "0000"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_and_revokes_old_token(client: AsyncClient) -> None:
    await _onboard_gym(client)
    login = await client.post(
        "/auth/staff/login", json={"phone": "+96170000001", "pin": "1234"}
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
        "/auth/staff/login", json={"phone": "+96170000001", "pin": "1234"}
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
        "/auth/staff/login", json={"phone": "+96170000001", "pin": "1234"}
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
