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
) -> dict[str, str]:
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
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _create_video(
    client: AsyncClient, headers: dict[str, str], *, title_en: str = "Bench Press"
) -> str:
    response = await client.post(
        "/videos",
        headers=_idem(headers),
        json={
            "title": {"ar": title_en, "en": title_en},
            "provider": "youtube",
            "external_id": "abc123",
            "muscle_group": "chest",
            "equipment": "barbell",
            "seconds": 200,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_create_and_list_videos(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="videos-a")
    video_id = await _create_video(client, headers)

    listed = await client.get("/videos", headers=headers)
    assert listed.status_code == 200
    assert any(v["id"] == video_id for v in listed.json())


async def test_get_video_increments_view_count(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="videos-b")
    video_id = await _create_video(client, headers)

    first = await client.get(f"/videos/{video_id}", headers=headers)
    assert first.status_code == 200
    assert first.json()["view_count"] == 1

    second = await client.get(f"/videos/{video_id}", headers=headers)
    assert second.json()["view_count"] == 2


async def test_update_video(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="videos-c")
    video_id = await _create_video(client, headers)

    updated = await client.patch(
        f"/videos/{video_id}", headers=_idem(headers), json={"muscle_group": "back"}
    )
    assert updated.status_code == 200
    assert updated.json()["muscle_group"] == "back"


async def test_deactivated_video_disappears_from_list(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="videos-d")
    video_id = await _create_video(client, headers)

    await client.patch(f"/videos/{video_id}", headers=_idem(headers), json={"active": False})

    listed = await client.get("/videos", headers=headers)
    assert all(v["id"] != video_id for v in listed.json())


async def test_get_missing_video_404s(client: AsyncClient) -> None:
    _gym_id, headers = await _gym_and_staff_token(client, slug="videos-e")
    response = await client.get(f"/videos/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_member_can_list_and_view_but_not_create(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="videos-f")
    video_id = await _create_video(client, staff_headers)
    member_headers = await _member_token(client, gym_id, staff_headers, phone="+96170500010")

    listed = await client.get("/videos", headers=member_headers)
    assert listed.status_code == 200
    assert any(v["id"] == video_id for v in listed.json())

    viewed = await client.get(f"/videos/{video_id}", headers=member_headers)
    assert viewed.status_code == 200

    forbidden = await client.post(
        "/videos",
        headers=_idem(member_headers),
        json={
            "title": {"ar": "x", "en": "x"}, "provider": "youtube", "external_id": "x",
            "muscle_group": "chest", "equipment": "barbell", "seconds": 100,
        },
    )
    assert forbidden.status_code == 403
