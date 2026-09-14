import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import get_owner_sessionmaker, tenant_session
from app.models import CheckIn, Member

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"


async def _gym_and_staff_token(client: AsyncClient) -> tuple[uuid.UUID, dict[str, str]]:
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": "idem-gym",
            "manager_name": "Manager", "manager_phone": "+96170000009",
            "manager_pin": "1234",
        },
    )
    assert onboard.status_code == 201, onboard.text
    gym_id = uuid.UUID(onboard.json()["gym_id"])

    login = await client.post(
        "/auth/staff/login", json={"phone": "+96170000009", "pin": "1234"}
    )
    token = login.json()["access_token"]
    return gym_id, {"Authorization": f"Bearer {token}"}


async def _insert_member(gym_id: uuid.UUID, *, phone: str) -> uuid.UUID:
    member_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Member",
                phone=phone, joined_at=datetime.now(UTC),
            )
        )
    return member_id


async def _check_in_count(gym_id: uuid.UUID) -> int:
    sessionmaker = get_owner_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(
            select(func.count()).select_from(CheckIn).where(CheckIn.gym_id == gym_id)
        )
        return result.scalar_one()


async def test_missing_idempotency_key_rejected(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client)
    member_id = await _insert_member(gym_id, phone="+96173333331")
    response = await client.post(
        "/check-ins", headers=headers, json={"member_id": str(member_id)}
    )
    assert response.status_code == 400


async def test_repeated_key_same_body_replays_and_writes_once(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client)
    member_id = await _insert_member(gym_id, phone="+96173333332")
    headers = {**headers, "Idempotency-Key": "fixed-key-1"}
    body = {"member_id": str(member_id)}

    first = await client.post("/check-ins", headers=headers, json=body)
    assert first.status_code == 201, first.text
    check_in_id = first.json()["id"]

    for _ in range(2):
        repeat = await client.post("/check-ins", headers=headers, json=body)
        assert repeat.status_code == 201
        assert repeat.json()["id"] == check_in_id

    assert await _check_in_count(gym_id) == 1


async def test_repeated_key_different_body_conflicts(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client)
    member_a = await _insert_member(gym_id, phone="+96173333333")
    member_b = await _insert_member(gym_id, phone="+96173333334")
    headers = {**headers, "Idempotency-Key": "fixed-key-2"}

    first = await client.post(
        "/check-ins", headers=headers, json={"member_id": str(member_a)}
    )
    assert first.status_code == 201

    conflict = await client.post(
        "/check-ins", headers=headers, json={"member_id": str(member_b)}
    )
    assert conflict.status_code == 409
    assert await _check_in_count(gym_id) == 1


async def test_different_keys_create_separate_rows(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client)
    member_id = await _insert_member(gym_id, phone="+96173333335")
    body = {"member_id": str(member_id)}

    first = await client.post(
        "/check-ins", headers={**headers, "Idempotency-Key": "key-a"}, json=body
    )
    second = await client.post(
        "/check-ins", headers={**headers, "Idempotency-Key": "key-b"}, json=body
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert await _check_in_count(gym_id) == 2
