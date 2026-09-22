"""Phase 4 stage 7: GET /members/{id} and GET /members/{id}/today-workout
broadened to accept a member caller asking about themselves (decision 2's
"broaden, don't duplicate" pattern). These tests prove the ownership
check that broadening required — cross-member reads were never possible
before because only staff ever called these routes.
"""

import itertools
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote

from httpx import AsyncClient

from app.db import tenant_session
from app.models import Member

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


async def test_member_can_read_their_own_detail(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="self-a")
    member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170100001"
    )

    response = await client.get(f"/members/{member_id}", headers=member_headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(member_id)


async def test_member_cannot_read_another_members_detail(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="self-b")
    a_id, _a_headers = await _member_token(client, gym_id, staff_headers, phone="+96170100002")
    _b_id, b_headers = await _member_token(client, gym_id, staff_headers, phone="+96170100003")

    response = await client.get(f"/members/{a_id}", headers=b_headers)
    assert response.status_code == 404


async def test_member_can_read_their_own_today_workout(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="self-c")
    member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170100004"
    )

    response = await client.get(f"/members/{member_id}/today-workout", headers=member_headers)
    assert response.status_code == 200
    assert response.json()["exercises"] == []


async def test_member_cannot_read_another_members_today_workout(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="self-d")
    a_id, _a_headers = await _member_token(client, gym_id, staff_headers, phone="+96170100005")
    _b_id, b_headers = await _member_token(client, gym_id, staff_headers, phone="+96170100006")

    response = await client.get(f"/members/{a_id}/today-workout", headers=b_headers)
    assert response.status_code == 404


async def test_staff_can_still_read_any_member_detail(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="self-e")
    member_id, _member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170100007"
    )

    response = await client.get(f"/members/{member_id}", headers=staff_headers)
    assert response.status_code == 200
