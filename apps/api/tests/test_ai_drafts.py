import itertools
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote

from httpx import AsyncClient

from app.db import tenant_session
from app.models import AiPlanDraft, Member, MemberProfile, MemberProgram

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


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _insert_member(gym_id: uuid.UUID, *, weight_kg: float = 75.0) -> tuple[uuid.UUID, str]:
    member_id = uuid.uuid4()
    phone = f"+96170600{next(_counter):03d}"
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
                height_cm=175, weight_kg=weight_kg, injuries=[], days_per_week=3,
                job="desk", sleep_hours=7.0, weight_trend=[],
            )
        )
    return member_id, phone


async def _member_token(
    client: AsyncClient, member_id: uuid.UUID, phone: str, staff_headers: dict[str, str]
) -> dict[str, str]:
    code_response = await client.post(f"/auth/member/{member_id}/code", headers=staff_headers)
    wa_link = unquote(code_response.json()["wa_link"])
    match = re.search(r"code is (\d{6})", wa_link)
    assert match is not None
    login = await client.post(
        "/auth/member/login", json={"phone": phone, "code": match.group(1)}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _insert_draft(
    gym_id: uuid.UUID, member_id: uuid.UUID, *, kind: str = "tip", payload: dict | None = None
) -> uuid.UUID:
    draft_id = uuid.uuid4()
    async with tenant_session(gym_id) as session:
        session.add(
            AiPlanDraft(
                id=draft_id, gym_id=gym_id, member_id=member_id, created_by="coach_plan",
                kind=kind, headline={"ar": "أ", "en": "Headline"},
                body={"ar": "ب", "en": "Body"}, reason={"ar": "س", "en": "Reason"},
                payload=payload,
            )
        )
    return draft_id


async def test_list_ai_drafts(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="drafts-list")
    member_id, _phone = await _insert_member(gym_id)
    draft_id = await _insert_draft(gym_id, member_id)

    listed = await client.get("/ai-drafts", headers=headers)
    assert listed.status_code == 200
    assert any(d["id"] == str(draft_id) for d in listed.json())


async def test_reject_a_draft(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="drafts-reject")
    member_id, _phone = await _insert_member(gym_id)
    draft_id = await _insert_draft(gym_id, member_id)

    response = await client.post(f"/ai-drafts/{draft_id}/reject", headers=_idem(headers))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"


async def test_approve_a_tip_draft_is_status_only(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="drafts-tip")
    member_id, _phone = await _insert_member(gym_id)
    draft_id = await _insert_draft(gym_id, member_id, kind="tip")

    response = await client.post(f"/ai-drafts/{draft_id}/approve", headers=_idem(headers), json={})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert response.json()["original"] is None


async def test_approve_a_nutrition_draft_sets_the_calorie_target(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="drafts-nutrition")
    member_id, _phone = await _insert_member(gym_id, weight_kg=80.0)
    draft_id = await _insert_draft(
        gym_id, member_id, kind="nutrition",
        payload={"type": "calorie_target_update", "daily_kcal_target": 1900},
    )

    response = await client.post(f"/ai-drafts/{draft_id}/approve", headers=_idem(headers), json={})
    assert response.status_code == 200, response.text

    member_detail = await client.get(f"/members/{member_id}", headers=headers)
    assert member_detail.json()["profile"]["daily_kcal_target"] == 1900


async def test_approve_a_plan_draft_archives_the_old_program_and_creates_a_new_one(
    client: AsyncClient,
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="drafts-plan")
    member_id, _phone = await _insert_member(gym_id)

    exercise = await client.post(
        "/exercises",
        headers=_idem(headers),
        json={"name": {"ar": "سكوات", "en": "Squat"}, "muscle_group": "legs"},
    )
    exercise_id = exercise.json()["id"]
    old_program = await client.post(
        f"/members/{member_id}/programs",
        headers=_idem(headers),
        json={"title": {"ar": "أ", "en": "Old"}, "exercises": []},
    )
    old_program_id = old_program.json()["id"]

    draft_id = await _insert_draft(
        gym_id, member_id, kind="plan",
        payload={
            "type": "program_exercise_update",
            "title": {"ar": "جديد", "en": "New Plan"},
            "exercises": [
                {"exercise_id": exercise_id, "sets": 3, "reps": {"ar": "١٠", "en": "10"}}
            ],
        },
    )

    response = await client.post(f"/ai-drafts/{draft_id}/approve", headers=_idem(headers), json={})
    assert response.status_code == 200, response.text

    active = await client.get(f"/members/{member_id}/programs/active", headers=headers)
    assert active.json()["title"]["en"] == "New Plan"
    assert len(active.json()["exercises"]) == 1

    async with tenant_session(gym_id) as session:
        old = await session.get(MemberProgram, uuid.UUID(old_program_id))
        assert old is not None and old.archived_at is not None


async def test_approve_records_original_only_on_first_edit(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="drafts-edit")
    member_id, _phone = await _insert_member(gym_id)
    draft_id = await _insert_draft(gym_id, member_id, kind="tip")

    response = await client.post(
        f"/ai-drafts/{draft_id}/approve",
        headers=_idem(headers),
        json={"body": {"ar": "ب٢", "en": "Edited body"}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"]["en"] == "Edited body"
    assert body["original"] is not None
    assert body["original"]["body"]["en"] == "Body"


async def test_approving_an_already_decided_draft_400s(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="drafts-twice")
    member_id, _phone = await _insert_member(gym_id)
    draft_id = await _insert_draft(gym_id, member_id, kind="tip")

    await client.post(f"/ai-drafts/{draft_id}/approve", headers=_idem(headers), json={})
    second = await client.post(f"/ai-drafts/{draft_id}/approve", headers=_idem(headers), json={})
    assert second.status_code == 400


async def test_member_cannot_reach_ai_drafts(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="drafts-member")
    member_id, phone = await _insert_member(gym_id)
    await _insert_draft(gym_id, member_id)
    member_headers = await _member_token(client, member_id, phone, staff_headers)

    forbidden = await client.get("/ai-drafts", headers=member_headers)
    assert forbidden.status_code == 403


async def test_ai_plan_drafts_never_show_the_other_gym(client: AsyncClient) -> None:
    gym_a, headers_a = await _gym_and_staff_token(client, slug="drafts-iso-a")
    gym_b, headers_b = await _gym_and_staff_token(client, slug="drafts-iso-b")
    member_a, _phone_a = await _insert_member(gym_a)
    member_b, _phone_b = await _insert_member(gym_b)
    draft_a = await _insert_draft(gym_a, member_a)
    draft_b = await _insert_draft(gym_b, member_b)

    listed_a = await client.get("/ai-drafts", headers=headers_a)
    ids_a = {d["id"] for d in listed_a.json()}
    assert str(draft_a) in ids_a
    assert str(draft_b) not in ids_a
