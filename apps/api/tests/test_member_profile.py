"""PATCH /members/me/profile — a member editing their own body/lifestyle
data (Phase 5 stage 5). Deliberately separate from staff's
PATCH /members/{id}: excludes name/phone (staff-only) and
daily_kcal_target (coach/AI-approval-only, app/api/ai_drafts.py).
"""

import itertools
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote

from httpx import AsyncClient

from app.db import tenant_session
from app.models import Member, MemberProfile

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
        await session.flush()
        session.add(
            MemberProfile(
                member_id=member_id, gym_id=gym_id, goal="strength", level="mid",
                height_cm=175, weight_kg=75.0, injuries=[], days_per_week=3,
                job="desk", sleep_hours=7.0, weight_trend=[],
            )
        )

    code_response = await client.post(f"/auth/member/{member_id}/code", headers=staff_headers)
    wa_link = unquote(code_response.json()["wa_link"])
    match = re.search(r"code is (\d{6})", wa_link)
    assert match is not None
    login = await client.post(
        "/auth/member/login", json={"phone": phone, "code": match.group(1)}
    )
    assert login.status_code == 200, login.text
    return member_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def test_member_can_update_their_own_profile(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="profile-a")
    _member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170200001"
    )

    response = await client.patch(
        "/members/me/profile",
        headers=_idem(member_headers),
        json={
            "sleep_hours": 6.5,
            "job": "shift",
            "injuries": [
                {"body_part": "knee_left", "note": {"ar": "ركبة", "en": "Knee"}, "severity": "mild"}
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sleep_hours"] == 6.5
    assert body["job"] == "shift"
    assert body["injuries"] == [
        {"body_part": "knee_left", "note": {"ar": "ركبة", "en": "Knee"}, "severity": "mild"}
    ]


async def test_member_cannot_set_their_own_daily_kcal_target(client: AsyncClient) -> None:
    """UpdateMyProfileRequest has no daily_kcal_target field at all — a
    request body naming it is silently ignored (pydantic's default extra
    behavior), so the real assertion is that the stored value never
    changes, not that the request is rejected."""
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="profile-b")
    member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170200002"
    )

    response = await client.patch(
        "/members/me/profile",
        headers=_idem(member_headers),
        json={"daily_kcal_target": 1200},
    )
    assert response.status_code == 200, response.text
    assert response.json()["daily_kcal_target"] is None

    async with tenant_session(gym_id) as session:
        profile = await session.get(MemberProfile, member_id)
        assert profile is not None and profile.daily_kcal_target is None


async def test_member_cannot_update_another_members_profile_via_name_or_phone(
    client: AsyncClient,
) -> None:
    """UpdateMyProfileRequest has no name/phone fields — a request naming
    them is silently ignored, same reasoning as the calorie-target test."""
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="profile-c")
    member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170200003"
    )

    response = await client.patch(
        "/members/me/profile",
        headers=_idem(member_headers),
        json={"name": "Hijacked", "phone": "+96170000000"},
    )
    assert response.status_code == 200, response.text

    async with tenant_session(gym_id) as session:
        member = await session.get(Member, member_id)
        assert member is not None and member.name != "Hijacked" and member.phone != "+96170000000"


async def test_staff_cannot_reach_the_member_profile_endpoint(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="profile-d")
    await _member_token(client, gym_id, staff_headers, phone="+96170200004")

    response = await client.patch(
        "/members/me/profile", headers=_idem(staff_headers), json={"sleep_hours": 6.0}
    )
    assert response.status_code == 403


async def test_member_profile_updates_never_cross_gyms(client: AsyncClient) -> None:
    gym_a, staff_a = await _gym_and_staff_token(client, slug="profile-iso-a")
    gym_b, staff_b = await _gym_and_staff_token(client, slug="profile-iso-b")
    member_a, headers_a = await _member_token(client, gym_a, staff_a, phone="+96170200005")
    member_b, _headers_b = await _member_token(client, gym_b, staff_b, phone="+96170200006")

    await client.patch(
        "/members/me/profile", headers=_idem(headers_a), json={"sleep_hours": 5.0}
    )

    async with tenant_session(gym_b) as session:
        profile_b = await session.get(MemberProfile, member_b)
        assert profile_b is not None and float(profile_b.sleep_hours) == 7.0

    async with tenant_session(gym_a) as session:
        profile_a = await session.get(MemberProfile, member_a)
        assert profile_a is not None and float(profile_a.sleep_hours) == 5.0
