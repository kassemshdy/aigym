"""The two member-facing chat assistants (decision 10) — the hardest part
of Phase 5 per the roadmap's own framing, since they talk to members
directly rather than through a coach.

No server-side chat-history table: a documented scope cut, not an
oversight. The client already carries enough turn history for a
stateless per-turn call (matching how the mock version's replyTo() always
worked), and a durable transcript (gym-scoped, RLS, retention questions)
isn't asked for anywhere in Phase 5's actual requirements — see
docs/DECISIONS.md, decision 29.

Chat-originated drafts never carry a structured payload (unlike Stage 9's
coach-generated ones) — deliberately. A casual chat message doesn't give
the model enough to reliably produce a validated program_exercise_update
(real exercise ids from the catalog) or calorie_target_update; asking it
to would be exactly the kind of unvalidated write decision 10 exists to
prevent. Every chat draft is `kind` + a bilingual-ish headline/body/reason
the coach reads and acts on by hand — status-only until approved, same as
any kind='tip' draft. The numeric guardrails (check_injury_contraindication,
check_calorie_floor) apply to Stage 9's structured, coach-triggered drafts
instead, where there is something concrete to check.

Headline/body/reason are stored under both the 'ar' and 'en' keys with
the SAME text (whichever language the member actually wrote in) — no
live translation in scope, same "no second-language version to keep in
sync" reasoning FoodEntry.label already accepts. A coach reading a chat
draft in their non-matching UI language sees the member's own words, not
a translation.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from anthropic.types import MessageParam
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.ai.client import AiUnavailable, AnthropicNotConfigured, run_structured
from app.ai.gather import (
    gather_gym_catalog,
    gather_member_context,
    gather_recent_sessions,
    gather_today_food,
)
from app.ai.models import HAIKU_MODEL
from app.deps import CurrentMember, CurrentSession
from app.domain.ai_context import build_system_prompt
from app.domain.guardrails import REFERRAL_TEXT, is_obviously_medical
from app.models import AiPlanDraft, FoodEntry

router = APIRouter(tags=["chat"])

Agent = Literal["nutrition", "training"]
Lang = Literal["ar", "en"]

_LANG_NAME = {"ar": "Arabic", "en": "English"}

_PERSONA: dict[Agent, str] = {
    "nutrition": (
        "You are AIGym's nutrition assistant for a Lebanese gym member, replying in "
        "{lang_name}. Answer nutrition and calorie questions directly and practically. "
        "If the member reports eating something, set `food` with your best estimate "
        "(kcal/protein/carbs/fat) — logging what they report is within your authority. "
        "You must NEVER claim to change the member's daily calorie target or training "
        "program yourself — you have no such authority. If they ask for that, acknowledge "
        "the request, set `draft` with a short kind ('nutrition' for a target change, "
        "'tip' otherwise), headline, body, and reason summarizing what they want, and tell "
        "them in `text` that you've sent it to their coach for review. Never say the change "
        "is already made. For anything that sounds like a medical question (symptoms, "
        "medication, an injury that needs a diagnosis), set `referred` to true instead of "
        "answering it yourself."
    ),
    "training": (
        "You are AIGym's bodybuilding/training assistant for a Lebanese gym member, "
        "replying in {lang_name}. Answer training, form, and recovery questions directly, "
        "taking the member's recorded injuries and recent sessions into account — never "
        "recommend an exercise that risks a recorded injury area. You must NEVER claim to "
        "change the member's training program yourself. If they ask for that (more weight, "
        "a new exercise, a program change), acknowledge the request, set `draft` with kind "
        "'plan', a headline, body, and reason summarizing what they want, and tell them in "
        "`text` that you've sent it to their coach for review. Never say the change is "
        "already made. For anything that sounds like a medical question, set `referred` to "
        "true instead of answering it yourself."
    ),
}


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatRequest(BaseModel):
    text: str
    history: list[ChatTurn] = []
    lang: Lang = "en"


class FoodProposal(BaseModel):
    label: str
    kcal: int
    protein: int
    carbs: int
    fat: int


class DraftProposal(BaseModel):
    kind: Literal["plan", "nutrition", "tip"]
    headline: str
    body: str
    reason: str


class ChatReply(BaseModel):
    """The model's structured output — response_model for run_structured."""

    text: str
    food: FoodProposal | None = None
    draft: DraftProposal | None = None
    referred: bool = False


class ChatReplyOut(BaseModel):
    """What the member's browser actually gets back — draft collapses to a
    bool, since the frontend only needs to know a suggestion was sent, not
    its content (that lives in the coach's inbox)."""

    text: str
    food: FoodProposal | None
    draft: bool
    referred: bool


def _referral(lang: Lang) -> ChatReplyOut:
    return ChatReplyOut(text=REFERRAL_TEXT[lang], food=None, draft=False, referred=True)


@router.post("/members/me/chat/{agent}", response_model=ChatReplyOut)
async def send_chat_message(
    agent: Agent, body: ChatRequest, session: CurrentSession, claims: CurrentMember
) -> ChatReplyOut:
    # Deterministic pre-filter, before any API call — catches the obvious
    # cases for free and short-circuits the whole flow (roadmap: "checked
    # before a reply is sent, not requested in the prompt").
    if is_obviously_medical(body.text):
        return _referral(body.lang)

    profile = await gather_member_context(session, claims.subject_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    recent_sessions = await gather_recent_sessions(session, claims.subject_id, body.lang)
    today_food = await gather_today_food(session, claims.subject_id)
    exercises, videos = await gather_gym_catalog(session)

    persona = _PERSONA[agent].format(lang_name=_LANG_NAME[body.lang])
    system = build_system_prompt(
        persona_instructions=persona, lang=body.lang, exercises=exercises, videos=videos,
        profile=profile, recent_sessions=recent_sessions, today_food=today_food,
    )

    messages: list[MessageParam] = [
        {"role": turn.role, "content": turn.text} for turn in body.history
    ]
    messages.append({"role": "user", "content": body.text})

    try:
        reply = run_structured(
            model=HAIKU_MODEL, system=system, messages=messages, response_model=ChatReply,
            max_tokens=1024, purpose=f"chat_{agent}", gym_id=claims.gym_id,
        )
    except AnthropicNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI assistant is not configured"
        ) from exc
    except AiUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI assistant is temporarily unavailable"
        ) from exc

    # The structured `referred` signal, not the model's prose, decides —
    # same code-not-prompt pattern the pre-filter above already uses.
    if reply.referred:
        return _referral(body.lang)

    if reply.draft is not None:
        session.add(
            AiPlanDraft(
                id=uuid.uuid4(), gym_id=claims.gym_id, member_id=claims.subject_id,
                created_by=f"chat_{agent}", kind=reply.draft.kind,
                headline={"ar": reply.draft.headline, "en": reply.draft.headline},
                body={"ar": reply.draft.body, "en": reply.draft.body},
                reason={"ar": reply.draft.reason, "en": reply.draft.reason},
                payload=None,
            )
        )

    if reply.food is not None:
        session.add(
            FoodEntry(
                id=uuid.uuid4(), gym_id=claims.gym_id, member_id=claims.subject_id,
                at=datetime.now(UTC), label=reply.food.label, kcal=reply.food.kcal,
                protein=reply.food.protein, carbs=reply.food.carbs, fat=reply.food.fat,
                source="agent",
            )
        )

    await session.flush()
    return ChatReplyOut(
        text=reply.text, food=reply.food, draft=reply.draft is not None, referred=False,
    )
