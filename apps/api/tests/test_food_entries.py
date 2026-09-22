import itertools
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

import pytest
from httpx import AsyncClient

import app.api.food_entries as food_entries_module
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


def _entry_payload(label: str = "Chicken and rice") -> dict[str, object]:
    return {
        "label": label, "kcal": 500, "protein": 40, "carbs": 50, "fat": 15, "source": "manual",
    }


async def test_create_and_list_own_food_entries(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-a")
    member_headers = await _member_token(client, gym_id, staff_headers, phone="+96170600001")

    created = await client.post(
        "/members/me/food-entries", headers=_idem(member_headers), json=_entry_payload()
    )
    assert created.status_code == 201, created.text
    assert created.json()["label"] == "Chicken and rice"

    listed = await client.get("/members/me/food-entries", headers=member_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_food_entry_with_photo_key(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-b")
    member_headers = await _member_token(client, gym_id, staff_headers, phone="+96170600002")

    upload = await client.post(
        "/media",
        headers=_idem(member_headers),
        files={"file": ("meal.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert upload.status_code == 201, upload.text
    photo_key = upload.json()["key"]

    created = await client.post(
        "/members/me/food-entries",
        headers=_idem(member_headers),
        json={**_entry_payload(), "source": "photo", "photo_key": photo_key,
              "estimate": {"kcal": 480, "protein": 38, "carbs": 48, "fat": 14}},
    )
    assert created.status_code == 201, created.text
    assert created.json()["photo_key"] == photo_key

    media = await client.get(f"/media/{photo_key}", headers=member_headers)
    assert media.status_code == 200
    assert media.content == b"fake-jpeg-bytes"


async def test_delete_own_food_entry(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-c")
    member_headers = await _member_token(client, gym_id, staff_headers, phone="+96170600003")

    created = await client.post(
        "/members/me/food-entries", headers=_idem(member_headers), json=_entry_payload()
    )
    entry_id = created.json()["id"]

    deleted = await client.delete(
        f"/members/me/food-entries/{entry_id}", headers=_idem(member_headers)
    )
    assert deleted.status_code == 204

    listed = await client.get("/members/me/food-entries", headers=member_headers)
    assert listed.json() == []


async def test_a_member_cannot_see_or_delete_another_members_food_entries(
    client: AsyncClient,
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-d")
    a_headers = await _member_token(client, gym_id, staff_headers, phone="+96170600004")
    b_headers = await _member_token(client, gym_id, staff_headers, phone="+96170600005")

    created = await client.post(
        "/members/me/food-entries", headers=_idem(a_headers), json=_entry_payload()
    )
    entry_id = created.json()["id"]

    b_listed = await client.get("/members/me/food-entries", headers=b_headers)
    assert b_listed.json() == []

    b_deleted = await client.delete(
        f"/members/me/food-entries/{entry_id}", headers=_idem(b_headers)
    )
    assert b_deleted.status_code == 404

    a_listed = await client.get("/members/me/food-entries", headers=a_headers)
    assert len(a_listed.json()) == 1


async def test_staff_cannot_create_a_food_entry(client: AsyncClient) -> None:
    _gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-e")

    response = await client.post(
        "/members/me/food-entries", headers=_idem(staff_headers), json=_entry_payload()
    )
    assert response.status_code == 403


async def test_upload_rejects_unsupported_content_type(client: AsyncClient) -> None:
    _gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-f")

    response = await client.post(
        "/media",
        headers=_idem(staff_headers),
        files={"file": ("doc.pdf", b"not an image", "application/pdf")},
    )
    assert response.status_code == 415


async def _uploaded_photo_key(client: AsyncClient, member_headers: dict[str, str]) -> str:
    upload = await client.post(
        "/media",
        headers=_idem(member_headers),
        files={"file": ("meal.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert upload.status_code == 201, upload.text
    return upload.json()["key"]


async def test_estimate_food_entry_returns_the_models_guess_without_writing_anything(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-vision-a")
    member_headers = await _member_token(client, gym_id, staff_headers, phone="+96170600006")
    photo_key = await _uploaded_photo_key(client, member_headers)

    def _fake_run_structured(**kwargs: Any) -> food_entries_module.FoodEstimateOut:
        assert kwargs["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"
        return food_entries_module.FoodEstimateOut(
            label="Grilled chicken with rice", kcal=620, protein=45, carbs=68, fat=14
        )

    monkeypatch.setattr(food_entries_module, "run_structured", _fake_run_structured)

    response = await client.post(
        "/members/me/food-entries/estimate",
        headers=_idem(member_headers),
        json={"photo_key": photo_key, "lang": "en"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "label": "Grilled chicken with rice", "kcal": 620, "protein": 45, "carbs": 68, "fat": 14,
    }

    listed = await client.get("/members/me/food-entries", headers=member_headers)
    assert listed.json() == []


async def test_estimate_with_unknown_photo_key_returns_404(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-vision-b")
    member_headers = await _member_token(client, gym_id, staff_headers, phone="+96170600007")

    response = await client.post(
        "/members/me/food-entries/estimate",
        headers=_idem(member_headers),
        json={"photo_key": "0" * 32 + ".jpg"},
    )
    assert response.status_code == 404


async def test_estimate_ai_not_configured_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-vision-c")
    member_headers = await _member_token(client, gym_id, staff_headers, phone="+96170600008")
    photo_key = await _uploaded_photo_key(client, member_headers)

    def _raise(**kwargs: Any) -> Any:
        raise food_entries_module.AnthropicNotConfigured("no key")

    monkeypatch.setattr(food_entries_module, "run_structured", _raise)

    response = await client.post(
        "/members/me/food-entries/estimate",
        headers=_idem(member_headers),
        json={"photo_key": photo_key},
    )
    assert response.status_code == 503


async def test_staff_cannot_call_estimate(client: AsyncClient) -> None:
    _gym_id, staff_headers = await _gym_and_staff_token(client, slug="food-vision-d")

    response = await client.post(
        "/members/me/food-entries/estimate",
        headers=_idem(staff_headers),
        json={"photo_key": "0" * 32 + ".jpg"},
    )
    assert response.status_code == 403
