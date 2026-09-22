import itertools
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

import pytest
from httpx import AsyncClient

import app.api.ai_drafts as ai_drafts_module
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


# ---------------------------------------------------------------------
# Phase 5 stage 9 — POST /members/{id}/ai-drafts/generate. Every test
# monkeypatches app.api.ai_drafts.run_structured, same no-real-call
# discipline as test_chat.py.
# ---------------------------------------------------------------------


async def _add_exercise(
    client: AsyncClient, headers: dict[str, str], *, name_en: str, muscle_group: str
) -> str:
    response = await client.post(
        "/exercises",
        headers=_idem(headers),
        json={"name": {"ar": name_en, "en": name_en}, "muscle_group": muscle_group},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _fake_run(responses: dict[type, Any]):  # noqa: ANN201 - test helper
    def _run(*, response_model: type, **kwargs: Any) -> Any:
        return responses[response_model]

    return _run


async def test_generate_plan_writes_a_pending_plan_draft_with_a_real_exercise_id(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="gen-plan-a")
    member_id, _phone = await _insert_member(gym_id)
    exercise_id = await _add_exercise(client, headers, name_en="Leg Press", muscle_group="legs")

    plan = ai_drafts_module.GeneratedPlan(
        headline="New plan", body="A 4-exercise plan", reason="Matches their goal",
        title="Strength block",
        exercises=[
            ai_drafts_module.GeneratedExercise(catalog_index=0, sets=3, reps="8-12")
        ],
    )
    monkeypatch.setattr(
        ai_drafts_module, "run_structured", _fake_run({ai_drafts_module.GeneratedPlan: plan})
    )

    response = await client.post(
        f"/members/{member_id}/ai-drafts/generate",
        headers=_idem(headers),
        json={"kind": "plan", "lang": "en"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "plan"
    assert body["status"] == "pending"
    assert body["payload"]["type"] == "program_exercise_update"
    assert body["payload"]["exercises"] == [
        {"exercise_id": exercise_id, "sets": 3, "reps": {"ar": "8-12", "en": "8-12"},
         "target_weight_kg": None}
    ]


async def test_generate_plan_drops_injury_contraindicated_exercises_and_falls_back_to_a_tip(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="gen-plan-b")
    member_id = uuid.uuid4()
    phone = f"+96170600{next(_counter):03d}"
    async with tenant_session(gym_id) as session:
        session.add(
            Member(
                id=member_id, gym_id=gym_id, name="عضو", name_en="Injured Member",
                phone=phone, joined_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            MemberProfile(
                member_id=member_id, gym_id=gym_id, goal="strength", level="mid",
                height_cm=175, weight_kg=75.0,
                injuries=[{"body_part": "lower_back", "note": {"ar": "ظهر", "en": "back"},
                           "severity": "moderate"}],
                days_per_week=3, job="desk", sleep_hours=7.0, weight_trend=[],
            )
        )
    await _add_exercise(client, headers, name_en="Squat", muscle_group="legs")

    plan = ai_drafts_module.GeneratedPlan(
        headline="New plan", body="A squat-heavy plan", reason="Matches their goal",
        title="Legs block",
        exercises=[
            ai_drafts_module.GeneratedExercise(catalog_index=0, sets=3, reps="8-12")
        ],
    )
    monkeypatch.setattr(
        ai_drafts_module, "run_structured", _fake_run({ai_drafts_module.GeneratedPlan: plan})
    )

    response = await client.post(
        f"/members/{member_id}/ai-drafts/generate",
        headers=_idem(headers),
        json={"kind": "plan", "lang": "en"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "tip"
    assert body["payload"] is None
    assert "injur" in body["reason"]["en"].lower()


async def test_generate_nutrition_clamps_a_target_below_the_calorie_floor(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="gen-nutrition-a")
    member_id, _phone = await _insert_member(gym_id, weight_kg=80.0)

    nutrition = ai_drafts_module.GeneratedNutrition(
        headline="Cut calories", body="Aggressive deficit", reason="Fast weight loss goal",
        daily_kcal_target=900,
    )
    monkeypatch.setattr(
        ai_drafts_module, "run_structured",
        _fake_run({ai_drafts_module.GeneratedNutrition: nutrition}),
    )

    response = await client.post(
        f"/members/{member_id}/ai-drafts/generate",
        headers=_idem(headers),
        json={"kind": "nutrition", "lang": "en"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "nutrition"
    assert body["payload"] == {"type": "calorie_target_update", "daily_kcal_target": 1200}
    assert "1200" in body["reason"]["en"]


async def test_generate_nutrition_keeps_a_safe_target_unchanged(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="gen-nutrition-b")
    member_id, _phone = await _insert_member(gym_id, weight_kg=150.0)

    nutrition = ai_drafts_module.GeneratedNutrition(
        headline="New target", body="A sensible target", reason="Matches their weight",
        daily_kcal_target=2200,
    )
    monkeypatch.setattr(
        ai_drafts_module, "run_structured",
        _fake_run({ai_drafts_module.GeneratedNutrition: nutrition}),
    )

    response = await client.post(
        f"/members/{member_id}/ai-drafts/generate",
        headers=_idem(headers),
        json={"kind": "nutrition", "lang": "en"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["payload"] == {
        "type": "calorie_target_update", "daily_kcal_target": 2200
    }
    assert response.json()["reason"]["en"] == "Matches their weight"


async def test_generate_tip_writes_a_pending_tip_draft_with_no_payload(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="gen-tip")
    member_id, _phone = await _insert_member(gym_id)

    tip = ai_drafts_module.GeneratedTip(
        headline="Hydration reminder", body="Drink more water on training days",
        reason="Low water logging this week",
    )
    monkeypatch.setattr(
        ai_drafts_module, "run_structured", _fake_run({ai_drafts_module.GeneratedTip: tip})
    )

    response = await client.post(
        f"/members/{member_id}/ai-drafts/generate",
        headers=_idem(headers),
        json={"kind": "tip", "lang": "en"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "tip"
    assert body["status"] == "pending"
    assert body["payload"] is None
    assert body["headline"]["en"] == "Hydration reminder"


async def test_generate_for_a_member_with_no_profile_404s(client: AsyncClient) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="gen-no-profile")

    response = await client.post(
        f"/members/{uuid.uuid4()}/ai-drafts/generate",
        headers=_idem(headers),
        json={"kind": "tip"},
    )
    assert response.status_code == 404


async def test_member_cannot_call_generate(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="gen-member")
    member_id, phone = await _insert_member(gym_id)
    member_headers = await _member_token(client, member_id, phone, staff_headers)

    response = await client.post(
        f"/members/{member_id}/ai-drafts/generate",
        headers=_idem(member_headers),
        json={"kind": "tip"},
    )
    assert response.status_code == 403


async def test_generate_ai_not_configured_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, headers = await _gym_and_staff_token(client, slug="gen-unconfigured")
    member_id, _phone = await _insert_member(gym_id)

    def _raise(**kwargs: Any) -> Any:
        raise ai_drafts_module.AnthropicNotConfigured("no key")

    monkeypatch.setattr(ai_drafts_module, "run_structured", _raise)

    response = await client.post(
        f"/members/{member_id}/ai-drafts/generate",
        headers=_idem(headers),
        json={"kind": "tip"},
    )
    assert response.status_code == 503
