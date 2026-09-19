import re
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote

from httpx import AsyncClient

from app import storage
from app.db import tenant_session
from app.models import FoodEntry, Member, ProgressPhoto

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"


async def _onboard_gym(client: AsyncClient, *, slug: str) -> dict[str, str]:
    phone = f"+9617{abs(hash(slug)) % 10_000_000:07d}"
    response = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Manager", "manager_username": f"mgr-{slug}",
            "manager_password": "hunter22", "manager_phone": phone,
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, str] = response.json()
    return body


async def _staff_header(client: AsyncClient, *, slug: str) -> dict[str, str]:
    login = await client.post(
        "/auth/staff/login", json={"username": f"mgr-{slug}", "password": "hunter22"}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _insert_member(gym_id: uuid.UUID, *, phone: str) -> uuid.UUID:
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Test Member",
                phone=phone, joined_at=datetime.now(UTC),
            )
        )
    return member_id


async def _member_header(
    client: AsyncClient, staff_header: dict[str, str], *, member_id: uuid.UUID, phone: str
) -> dict[str, str]:
    code_response = await client.post(f"/auth/member/{member_id}/code", headers=staff_header)
    wa_link = unquote(code_response.json()["wa_link"])
    code = re.search(r"code is (\d{6})", wa_link).group(1)  # type: ignore[union-attr]
    login = await client.post("/auth/member/login", json={"phone": phone, "code": code})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_media_404s_for_unknown_key(client: AsyncClient) -> None:
    await _onboard_gym(client, slug="media-a")
    staff_header = await _staff_header(client, slug="media-a")
    response = await client.get(
        "/media/00000000000000000000000000000000.jpg", headers=staff_header
    )
    assert response.status_code == 404


async def test_owning_member_can_see_their_own_progress_photo(client: AsyncClient) -> None:
    onboarded = await _onboard_gym(client, slug="media-b")
    gym_id = uuid.UUID(onboarded["gym_id"])
    staff_header = await _staff_header(client, slug="media-b")
    member_id = await _insert_member(gym_id, phone="+96170500001")
    member_header = await _member_header(
        client, staff_header, member_id=member_id, phone="+96170500001"
    )

    key = storage.save(b"fake-photo-bytes", "image/jpeg")
    async with tenant_session(gym_id) as session:
        session.add(
            ProgressPhoto(
                id=uuid.uuid4(), gym_id=gym_id, member_id=member_id,
                at=datetime.now(UTC), photo_key=key, shared_with_coach=False,
            )
        )

    response = await client.get(f"/media/{key}", headers=member_header)
    assert response.status_code == 200
    assert response.content == b"fake-photo-bytes"
    assert response.headers["content-type"] == "image/jpeg"


async def test_unshared_progress_photo_404s_for_staff(client: AsyncClient) -> None:
    onboarded = await _onboard_gym(client, slug="media-c")
    gym_id = uuid.UUID(onboarded["gym_id"])
    staff_header = await _staff_header(client, slug="media-c")
    member_id = await _insert_member(gym_id, phone="+96170500002")

    key = storage.save(b"private", "image/jpeg")
    async with tenant_session(gym_id) as session:
        session.add(
            ProgressPhoto(
                id=uuid.uuid4(), gym_id=gym_id, member_id=member_id,
                at=datetime.now(UTC), photo_key=key, shared_with_coach=False,
            )
        )

    response = await client.get(f"/media/{key}", headers=staff_header)
    assert response.status_code == 404


async def test_shared_progress_photo_is_visible_to_staff(client: AsyncClient) -> None:
    onboarded = await _onboard_gym(client, slug="media-d")
    gym_id = uuid.UUID(onboarded["gym_id"])
    staff_header = await _staff_header(client, slug="media-d")
    member_id = await _insert_member(gym_id, phone="+96170500003")

    key = storage.save(b"shared", "image/jpeg")
    async with tenant_session(gym_id) as session:
        session.add(
            ProgressPhoto(
                id=uuid.uuid4(), gym_id=gym_id, member_id=member_id,
                at=datetime.now(UTC), photo_key=key, shared_with_coach=True,
            )
        )

    response = await client.get(f"/media/{key}", headers=staff_header)
    assert response.status_code == 200
    assert response.content == b"shared"


async def test_progress_photo_hidden_from_a_different_member(client: AsyncClient) -> None:
    onboarded = await _onboard_gym(client, slug="media-e")
    gym_id = uuid.UUID(onboarded["gym_id"])
    staff_header = await _staff_header(client, slug="media-e")
    owner_id = await _insert_member(gym_id, phone="+96170500004")
    other_id = await _insert_member(gym_id, phone="+96170500005")
    other_header = await _member_header(
        client, staff_header, member_id=other_id, phone="+96170500005"
    )

    key = storage.save(b"not-yours", "image/jpeg")
    async with tenant_session(gym_id) as session:
        session.add(
            ProgressPhoto(
                id=uuid.uuid4(), gym_id=gym_id, member_id=owner_id,
                at=datetime.now(UTC), photo_key=key, shared_with_coach=True,
            )
        )

    response = await client.get(f"/media/{key}", headers=other_header)
    assert response.status_code == 404


async def test_food_entry_photo_is_ordinary_log_data_visible_to_any_staff(
    client: AsyncClient,
) -> None:
    """Decision 11: food photos carry none of progress photos' privacy
    weight — no shared_with_coach flag, staff can always see them."""
    onboarded = await _onboard_gym(client, slug="media-f")
    gym_id = uuid.UUID(onboarded["gym_id"])
    staff_header = await _staff_header(client, slug="media-f")
    member_id = await _insert_member(gym_id, phone="+96170500006")

    key = storage.save(b"lunch", "image/jpeg")
    async with tenant_session(gym_id) as session:
        session.add(
            FoodEntry(
                id=uuid.uuid4(), gym_id=gym_id, member_id=member_id,
                at=datetime.now(UTC), label="Chicken and rice", kcal=500,
                protein=40, carbs=50, fat=15, source="photo", photo_key=key,
            )
        )

    response = await client.get(f"/media/{key}", headers=staff_header)
    assert response.status_code == 200
    assert response.content == b"lunch"
