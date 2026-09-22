"""Member chat assistants (Phase 5 stage 7). Every test monkeypatches
app.api.chat.run_structured — no real Anthropic call anywhere in this
suite, matching app/ai/client.py's own test discipline (see
test_ai_client.py).
"""

import itertools
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.api.chat as chat_module
from app.db import tenant_session
from app.models import AiPlanDraft, FoodEntry, Member, MemberProfile

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


async def _member_with_profile(
    client: AsyncClient,
    gym_id: uuid.UUID,
    staff_headers: dict[str, str],
    *,
    weight_kg: float = 78.0,
) -> tuple[uuid.UUID, dict[str, str]]:
    member_id = uuid.uuid4()
    phone = f"+96170800{next(_counter):03d}"
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
                height_cm=178, weight_kg=weight_kg, injuries=[], days_per_week=4,
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


def _fake_reply(**overrides: Any) -> chat_module.ChatReply:
    defaults: dict[str, Any] = {
        "text": "Here's an answer.", "food": None, "draft": None, "referred": False,
    }
    defaults.update(overrides)
    return chat_module.ChatReply(**defaults)


async def test_medical_text_never_calls_the_model(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="chat-medical")
    _member_id, member_headers = await _member_with_profile(client, gym_id, staff_headers)

    def _fail(**kwargs: Any) -> Any:
        raise AssertionError("run_structured must not be called for an obviously medical message")

    monkeypatch.setattr(chat_module, "run_structured", _fail)

    response = await client.post(
        "/members/me/chat/nutrition",
        headers=_idem(member_headers),
        json={"text": "I've had chest pain during workouts lately"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["referred"] is True
    assert body["draft"] is False
    assert body["food"] is None


async def test_plain_answer_is_returned_as_is(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="chat-plain")
    _member_id, member_headers = await _member_with_profile(client, gym_id, staff_headers)

    monkeypatch.setattr(
        chat_module, "run_structured", lambda **kw: _fake_reply(text="Eat more protein.")
    )

    response = await client.post(
        "/members/me/chat/nutrition",
        headers=_idem(member_headers),
        json={"text": "How much protein should I eat?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "Eat more protein."
    assert body["draft"] is False
    assert body["referred"] is False


async def test_food_proposal_creates_a_real_food_entry(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="chat-food")
    member_id, member_headers = await _member_with_profile(client, gym_id, staff_headers)

    food = chat_module.FoodProposal(
        label="Chicken and rice", kcal=620, protein=45, carbs=68, fat=14
    )
    monkeypatch.setattr(
        chat_module, "run_structured", lambda **kw: _fake_reply(text="Logged it.", food=food)
    )

    response = await client.post(
        "/members/me/chat/nutrition",
        headers=_idem(member_headers),
        json={"text": "I had chicken and rice for lunch"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["food"]["label"] == "Chicken and rice"

    async with tenant_session(gym_id) as session:
        result = await session.execute(select(FoodEntry).where(FoodEntry.member_id == member_id))
        entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].source == "agent"
    assert entries[0].kcal == 620


async def test_draft_proposal_creates_a_pending_ai_plan_draft_with_no_payload(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="chat-draft")
    member_id, member_headers = await _member_with_profile(client, gym_id, staff_headers)

    draft = chat_module.DraftProposal(
        kind="plan", headline="More bench weight", body="Wants +5kg on bench",
        reason="Asked directly in chat",
    )
    monkeypatch.setattr(
        chat_module, "run_structured",
        lambda **kw: _fake_reply(text="Sent to your coach.", draft=draft),
    )

    response = await client.post(
        "/members/me/chat/training",
        headers=_idem(member_headers),
        json={"text": "I want to add weight to my bench"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["draft"] is True
    assert "coach" in response.json()["text"].lower()

    async with tenant_session(gym_id) as session:
        result = await session.execute(
            select(AiPlanDraft).where(AiPlanDraft.member_id == member_id)
        )
        drafts = result.scalars().all()
    assert len(drafts) == 1
    assert drafts[0].status == "pending"
    assert drafts[0].created_by == "chat_training"
    assert drafts[0].kind == "plan"
    assert drafts[0].payload is None
    assert drafts[0].headline == {"ar": "More bench weight", "en": "More bench weight"}


async def test_model_signaled_referred_overrides_any_food_or_draft(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="chat-referred")
    member_id, member_headers = await _member_with_profile(client, gym_id, staff_headers)

    food = chat_module.FoodProposal(label="x", kcal=1, protein=1, carbs=1, fat=1)
    monkeypatch.setattr(
        chat_module, "run_structured",
        lambda **kw: _fake_reply(text="some prose", food=food, referred=True),
    )

    response = await client.post(
        "/members/me/chat/nutrition", headers=_idem(member_headers), json={"text": "vague question"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["referred"] is True
    assert body["food"] is None

    async with tenant_session(gym_id) as session:
        result = await session.execute(select(FoodEntry).where(FoodEntry.member_id == member_id))
        assert result.scalars().all() == []


async def test_ai_not_configured_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="chat-unconfigured")
    _member_id, member_headers = await _member_with_profile(client, gym_id, staff_headers)

    def _raise(**kwargs: Any) -> Any:
        raise chat_module.AnthropicNotConfigured("no key")

    monkeypatch.setattr(chat_module, "run_structured", _raise)

    response = await client.post(
        "/members/me/chat/nutrition", headers=_idem(member_headers), json={"text": "hi"}
    )
    assert response.status_code == 503


async def test_ai_unavailable_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="chat-unavailable")
    _member_id, member_headers = await _member_with_profile(client, gym_id, staff_headers)

    def _raise(**kwargs: Any) -> Any:
        raise chat_module.AiUnavailable("rate limited")

    monkeypatch.setattr(chat_module, "run_structured", _raise)

    response = await client.post(
        "/members/me/chat/nutrition", headers=_idem(member_headers), json={"text": "hi"}
    )
    assert response.status_code == 503


async def test_staff_cannot_reach_a_members_chat_endpoint(client: AsyncClient) -> None:
    gym_id, staff_headers = await _gym_and_staff_token(client, slug="chat-staff")
    await _member_with_profile(client, gym_id, staff_headers)

    response = await client.post(
        "/members/me/chat/nutrition", headers=_idem(staff_headers), json={"text": "hi"}
    )
    assert response.status_code == 403
