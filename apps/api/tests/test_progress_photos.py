import itertools
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote

from httpx import AsyncClient

from app import storage
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
            "name_ar": "نادي",
            "name_en": "Gym",
            "slug": slug,
            "manager_name": "Manager",
            "manager_username": manager_username,
            "manager_password": "hunter22",
            "manager_phone": f"+96179{next(_counter):06d}",
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
                id=member_id,
                gym_id=gym_id,
                name="عضو",
                name_en="Test Member",
                phone=phone,
                joined_at=datetime.now(UTC),
            )
        )

    code_response = await client.post(f"/auth/member/{member_id}/code", headers=staff_headers)
    wa_link = unquote(code_response.json()["wa_link"])
    code = re.search(r"code is (\d{6})", wa_link).group(1)  # type: ignore[union-attr]
    login = await client.post("/auth/member/login", json={"phone": phone, "code": code})
    assert login.status_code == 200, login.text
    return member_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _upload_photo(client: AsyncClient, headers: dict[str, str]) -> str:
    upload = await client.post(
        "/media", headers=_idem(headers), files={"file": ("p.jpg", b"photo-bytes", "image/jpeg")}
    )
    assert upload.status_code == 201, upload.text
    key: str = upload.json()["key"]
    return key


async def test_create_and_list_own_progress_photos(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="pp-a")
    _member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170700001"
    )
    key = await _upload_photo(client, member_headers)

    created = await client.post(
        "/members/me/progress-photos", headers=_idem(member_headers), json={"photo_key": key}
    )
    assert created.status_code == 201, created.text
    assert created.json()["shared_with_coach"] is False

    listed = await client.get("/members/me/progress-photos", headers=member_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_toggle_shared_with_coach(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="pp-b")
    member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170700002"
    )
    key = await _upload_photo(client, member_headers)

    created = await client.post(
        "/members/me/progress-photos", headers=_idem(member_headers), json={"photo_key": key}
    )
    photo_id = created.json()["id"]

    shared = await client.patch(
        f"/members/me/progress-photos/{photo_id}",
        headers=_idem(member_headers),
        json={"shared_with_coach": True},
    )
    assert shared.status_code == 200
    assert shared.json()["shared_with_coach"] is True

    staff_view = await client.get(f"/members/{member_id}/shared-photos", headers=staff_headers)
    assert staff_view.status_code == 200
    assert len(staff_view.json()) == 1

    unshared = await client.patch(
        f"/members/me/progress-photos/{photo_id}",
        headers=_idem(member_headers),
        json={"shared_with_coach": False},
    )
    assert unshared.json()["shared_with_coach"] is False

    staff_view_after = await client.get(
        f"/members/{member_id}/shared-photos", headers=staff_headers
    )
    assert staff_view_after.json() == []


async def test_delete_progress_photo_removes_the_stored_file(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="pp-c")
    _member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170700003"
    )
    key = await _upload_photo(client, member_headers)

    created = await client.post(
        "/members/me/progress-photos", headers=_idem(member_headers), json={"photo_key": key}
    )
    photo_id = created.json()["id"]

    assert storage.read(key) is not None

    deleted = await client.delete(
        f"/members/me/progress-photos/{photo_id}", headers=_idem(member_headers)
    )
    assert deleted.status_code == 204

    assert storage.read(key) is None
    listed = await client.get("/members/me/progress-photos", headers=member_headers)
    assert listed.json() == []


async def test_a_member_cannot_see_patch_or_delete_another_members_photo(
    client: AsyncClient,
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="pp-d")
    _a_id, a_headers = await _member_token(client, gym_id, staff_headers, phone="+96170700004")
    _b_id, b_headers = await _member_token(client, gym_id, staff_headers, phone="+96170700005")
    key = await _upload_photo(client, a_headers)

    created = await client.post(
        "/members/me/progress-photos", headers=_idem(a_headers), json={"photo_key": key}
    )
    photo_id = created.json()["id"]

    b_listed = await client.get("/members/me/progress-photos", headers=b_headers)
    assert b_listed.json() == []

    b_patch = await client.patch(
        f"/members/me/progress-photos/{photo_id}",
        headers=_idem(b_headers),
        json={"shared_with_coach": True},
    )
    assert b_patch.status_code == 404

    b_delete = await client.delete(
        f"/members/me/progress-photos/{photo_id}", headers=_idem(b_headers)
    )
    assert b_delete.status_code == 404

    a_listed = await client.get("/members/me/progress-photos", headers=a_headers)
    assert len(a_listed.json()) == 1


async def test_shared_photos_endpoint_never_returns_unshared_photos(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="pp-e")
    member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170700006"
    )
    key = await _upload_photo(client, member_headers)

    await client.post(
        "/members/me/progress-photos", headers=_idem(member_headers), json={"photo_key": key}
    )

    staff_view = await client.get(f"/members/{member_id}/shared-photos", headers=staff_headers)
    assert staff_view.status_code == 200
    assert staff_view.json() == []


async def test_member_cannot_use_the_staff_shared_photos_endpoint(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="pp-f")
    member_id, member_headers = await _member_token(
        client, gym_id, staff_headers, phone="+96170700007"
    )

    response = await client.get(f"/members/{member_id}/shared-photos", headers=member_headers)
    assert response.status_code == 403
