"""The coach's AI draft inbox (decision 10): nothing an assistant or a
coach's "generate" button proposes ever reaches a member's program or
calorie target directly — it lands here, pending, until a coach approves
it. One mechanism for both origins (decision 31) — see app/api/chat.py
(stage 7) and app/api/ai_drafts.py's generate route (stage 9) for the two
producers; this file is the single consumer both write into.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AiUnavailable, AnthropicNotConfigured, run_structured
from app.ai.gather import (
    gather_exercise_catalog_with_ids,
    gather_member_context,
    gather_recent_sessions,
    gather_today_food,
)
from app.ai.models import HAIKU_MODEL, SONNET_MODEL
from app.deps import CurrentSession, require_role
from app.domain.ai_context import format_member_data
from app.domain.ai_drafts import CalorieTargetUpdate, ProgramExerciseUpdate, apply_draft
from app.domain.guardrails import calorie_floor, check_calorie_floor, check_injury_contraindication
from app.models import AiPlanDraft, Exercise, Member, MemberProfile, MemberProgram, ProgramExercise
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["ai-drafts"])

ManagerOrCoach = Depends(require_role("super_admin", "manager", "coach"))

T = TypeVar("T", bound=BaseModel)

Kind = Literal["plan", "nutrition", "tip"]
Lang = Literal["ar", "en"]

_LANG_NAME = {"ar": "Arabic", "en": "English"}

_NO_SAFE_EXERCISES_REASON = {
    "ar": "ما لقينا تمارين آمنة نقترحها نظراً للإصابات المسجلة — لازم الكوتش يصمم البرنامج يدوي.",
    "en": "No exercises could be safely suggested given the member's recorded injuries — "
          "the coach should design this plan by hand.",
}

_FLOOR_NOTE = {
    "ar": " (تم رفعه للحد الآمن {kcal} سعرة.)",
    "en": " (adjusted up to a safe floor of {kcal} kcal.)",
}

_PLAN_PERSONA = (
    "You are AIGym's training-plan assistant, drafting a proposed workout program for a gym "
    "coach to review and approve — you never assign it to the member directly. Reply in "
    "{lang_name}. Pick exercises ONLY by their catalog_index from the numbered list below; "
    "never invent an exercise or use a catalog_index outside that list. Propose 4 to 6 "
    "exercises, 2 to 5 sets each, and a plain rep range like \"8-12\" per exercise. Take the "
    "member's goal, level, days per week, and recent session history into account. Write a "
    "short headline, a body describing the plan, a reason explaining why you built it this "
    "way, and a short program title, all in {lang_name}.\n\nExercise catalog:\n{catalog}"
)

_NUTRITION_PERSONA = (
    "You are AIGym's nutrition assistant, drafting a proposed daily calorie target for a gym "
    "coach to review and approve — you never set it for the member directly. Reply in "
    "{lang_name}. Take the member's goal, weight, and level into account and propose one "
    "realistic daily_kcal_target. Write a short headline, a body explaining the number, and a "
    "reason, all in {lang_name}."
)

_TIP_PERSONA = (
    "You are AIGym's assistant, drafting a short coaching tip for a gym coach to review "
    "before it reaches the member — you never send it directly. Reply in {lang_name}, based "
    "on the member's profile and recent sessions. Write a short headline, a body with the "
    "tip itself, and a reason explaining why you're suggesting it now, all in {lang_name}."
)


class GenerateDraftRequest(BaseModel):
    kind: Kind
    lang: Lang = "en"


class GeneratedExercise(BaseModel):
    catalog_index: int
    sets: int
    reps: str
    target_weight_kg: float | None = None


class GeneratedPlan(BaseModel):
    headline: str
    body: str
    reason: str
    title: str
    exercises: list[GeneratedExercise]


class GeneratedNutrition(BaseModel):
    headline: str
    body: str
    reason: str
    daily_kcal_target: int


class GeneratedTip(BaseModel):
    headline: str
    body: str
    reason: str


class AiPlanDraftOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    created_by: str
    kind: str
    headline: dict[str, Any]
    body: dict[str, Any]
    reason: dict[str, Any]
    payload: dict[str, Any] | None
    status: str
    decided_at: datetime | None
    original: dict[str, Any] | None


def _to_out(draft: AiPlanDraft) -> AiPlanDraftOut:
    return AiPlanDraftOut(
        id=draft.id, member_id=draft.member_id, created_by=draft.created_by, kind=draft.kind,
        headline=draft.headline, body=draft.body, reason=draft.reason, payload=draft.payload,
        status=draft.status, decided_at=draft.decided_at, original=draft.original,
    )


@router.get("/ai-drafts", response_model=list[AiPlanDraftOut])
async def list_ai_drafts(
    session: CurrentSession, _claims: AccessTokenClaims = ManagerOrCoach
) -> list[AiPlanDraftOut]:
    result = await session.execute(select(AiPlanDraft).order_by(AiPlanDraft.created_at.desc()))
    return [_to_out(d) for d in result.scalars().all()]


def _run(*, model: str, system: str, response_model: type[T], max_tokens: int,
          purpose: str, gym_id: uuid.UUID) -> T:
    try:
        return run_structured(
            model=model, system=system,
            messages=[{"role": "user", "content": "Generate it now."}],
            response_model=response_model, max_tokens=max_tokens,
            purpose=purpose, gym_id=gym_id,
        )
    except AnthropicNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI assistant is not configured"
        ) from exc
    except AiUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI assistant is temporarily unavailable"
        ) from exc


@router.post(
    "/members/{member_id}/ai-drafts/generate",
    response_model=AiPlanDraftOut,
    status_code=status.HTTP_201_CREATED,
)
async def generate_ai_draft(
    member_id: uuid.UUID,
    body: GenerateDraftRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> AiPlanDraftOut:
    """Decision 31: the same ai_plan_drafts mechanism as chat (stage 7),
    just triggered by a coach action instead of a member message — always
    writes pending, never auto-applies. Sonnet 5 is scoped to kind='plan'
    specifically (the genuinely reasoning-heavy case); nutrition/tip stay
    on Haiku. Unlike a chat draft, this one carries a real, validated
    payload — decision 10's guardrails (check_injury_contraindication,
    check_calorie_floor) run against it before it's ever written, since
    there is finally something structured to check."""
    profile = await gather_member_context(session, member_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member profile not found")
    recent_sessions = await gather_recent_sessions(session, member_id, body.lang)
    today_food = await gather_today_food(session, member_id)
    lang_name = _LANG_NAME[body.lang]
    member_text = format_member_data(profile, recent_sessions, today_food, body.lang)

    if body.kind == "plan":
        catalog = await gather_exercise_catalog_with_ids(session)
        if not catalog:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Gym has no active exercises")
        catalog_text = "\n".join(
            f"{i}: {e.name.get(body.lang, e.name.get('en', ''))} ({e.muscle_group})"
            for i, e in enumerate(catalog)
        )
        system = (
            f"{_PLAN_PERSONA.format(lang_name=lang_name, catalog=catalog_text)}\n\n{member_text}"
        )
        plan = _run(
            model=SONNET_MODEL, system=system, response_model=GeneratedPlan,
            max_tokens=1536, purpose="generate_plan", gym_id=claims.gym_id,
        )

        safe_exercises: list[dict[str, Any]] = []
        for item in plan.exercises:
            if not 0 <= item.catalog_index < len(catalog):
                continue
            exercise = catalog[item.catalog_index]
            name_en = exercise.name.get("en", "")
            guardrail = check_injury_contraindication(
                profile.injuries, muscle_group=exercise.muscle_group, name_en=name_en
            )
            if guardrail.blocked:
                continue
            safe_exercises.append(
                {
                    "exercise_id": str(exercise.id),
                    "sets": max(1, item.sets),
                    "reps": {"ar": item.reps, "en": item.reps},
                    "target_weight_kg": item.target_weight_kg,
                }
            )

        if safe_exercises:
            draft = AiPlanDraft(
                id=uuid.uuid4(), gym_id=claims.gym_id, member_id=member_id,
                created_by="generate_plan", kind="plan",
                headline={"ar": plan.headline, "en": plan.headline},
                body={"ar": plan.body, "en": plan.body},
                reason={"ar": plan.reason, "en": plan.reason},
                payload={
                    "type": "program_exercise_update",
                    "title": {"ar": plan.title, "en": plan.title},
                    "exercises": safe_exercises,
                },
            )
        else:
            draft = AiPlanDraft(
                id=uuid.uuid4(), gym_id=claims.gym_id, member_id=member_id,
                created_by="generate_plan", kind="tip",
                headline={"ar": plan.headline, "en": plan.headline},
                body={"ar": plan.body, "en": plan.body},
                reason=_NO_SAFE_EXERCISES_REASON,
                payload=None,
            )

    elif body.kind == "nutrition":
        system = f"{_NUTRITION_PERSONA.format(lang_name=lang_name)}\n\n{member_text}"
        nutrition = _run(
            model=HAIKU_MODEL, system=system, response_model=GeneratedNutrition,
            max_tokens=512, purpose="generate_nutrition", gym_id=claims.gym_id,
        )

        target = nutrition.daily_kcal_target
        reason_text = nutrition.reason
        floor_check = check_calorie_floor(weight_kg=profile.weight_kg, proposed_kcal=target)
        if floor_check.blocked:
            target = calorie_floor(profile.weight_kg)
            reason_text += _FLOOR_NOTE[body.lang].format(kcal=target)

        draft = AiPlanDraft(
            id=uuid.uuid4(), gym_id=claims.gym_id, member_id=member_id,
            created_by="generate_nutrition", kind="nutrition",
            headline={"ar": nutrition.headline, "en": nutrition.headline},
            body={"ar": nutrition.body, "en": nutrition.body},
            reason={"ar": reason_text, "en": reason_text},
            payload={"type": "calorie_target_update", "daily_kcal_target": target},
        )

    else:
        system = f"{_TIP_PERSONA.format(lang_name=lang_name)}\n\n{member_text}"
        tip = _run(
            model=HAIKU_MODEL, system=system, response_model=GeneratedTip,
            max_tokens=512, purpose="generate_tip", gym_id=claims.gym_id,
        )
        draft = AiPlanDraft(
            id=uuid.uuid4(), gym_id=claims.gym_id, member_id=member_id,
            created_by="generate_tip", kind="tip",
            headline={"ar": tip.headline, "en": tip.headline},
            body={"ar": tip.body, "en": tip.body},
            reason={"ar": tip.reason, "en": tip.reason},
            payload=None,
        )

    session.add(draft)
    await session.flush()
    return _to_out(draft)


async def _active_program(session: AsyncSession, member_id: uuid.UUID) -> MemberProgram | None:
    result = await session.execute(
        select(MemberProgram)
        .where(MemberProgram.member_id == member_id, MemberProgram.archived_at.is_(None))
        .order_by(MemberProgram.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _apply(
    session: AsyncSession, draft: AiPlanDraft, claims: AccessTokenClaims
) -> None:
    action = apply_draft(draft.payload)
    if action is None:
        return

    if isinstance(action, CalorieTargetUpdate):
        profile = await session.get(MemberProfile, draft.member_id)
        if profile is not None:
            profile.daily_kcal_target = action.daily_kcal_target
        return

    if isinstance(action, ProgramExerciseUpdate):
        current = await _active_program(session, draft.member_id)
        if current is not None:
            current.archived_at = datetime.now(UTC)
        program = MemberProgram(
            id=uuid.uuid4(), gym_id=claims.gym_id, member_id=draft.member_id,
            title=action.title, created_by_staff_id=claims.subject_id,
        )
        session.add(program)
        await session.flush()
        for order_index, spec in enumerate(action.exercises):
            exercise = await session.get(Exercise, spec.exercise_id)
            if exercise is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"Exercise {spec.exercise_id} not found"
                )
            session.add(
                ProgramExercise(
                    id=uuid.uuid4(), gym_id=claims.gym_id, program_id=program.id,
                    exercise_id=spec.exercise_id, order_index=order_index, sets=spec.sets,
                    reps=spec.reps, target_weight_kg=spec.target_weight_kg,
                )
            )


class ApproveDraftRequest(BaseModel):
    headline: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    reason: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None


@router.post("/ai-drafts/{draft_id}/approve", response_model=AiPlanDraftOut)
async def approve_ai_draft(
    draft_id: uuid.UUID,
    body: ApproveDraftRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrCoach,
) -> AiPlanDraftOut:
    draft = await session.get(AiPlanDraft, draft_id)
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    if draft.status != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Draft already decided")
    member = await session.get(Member, draft.member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    edits = {"headline": body.headline, "body": body.body, "reason": body.reason,
             "payload": body.payload}
    edited = any(v is not None and v != getattr(draft, k) for k, v in edits.items())
    if edited and draft.original is None:
        draft.original = {
            "headline": draft.headline, "body": draft.body,
            "reason": draft.reason, "payload": draft.payload,
        }
    for field, value in edits.items():
        if value is not None:
            setattr(draft, field, value)

    await _apply(session, draft, claims)

    draft.status = "approved"
    draft.decided_by_staff_id = claims.subject_id
    draft.decided_at = datetime.now(UTC)
    await session.flush()
    return _to_out(draft)


@router.post("/ai-drafts/{draft_id}/reject", response_model=AiPlanDraftOut)
async def reject_ai_draft(
    draft_id: uuid.UUID, session: CurrentSession, claims: AccessTokenClaims = ManagerOrCoach
) -> AiPlanDraftOut:
    draft = await session.get(AiPlanDraft, draft_id)
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    if draft.status != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Draft already decided")

    draft.status = "rejected"
    draft.decided_by_staff_id = claims.subject_id
    draft.decided_at = datetime.now(UTC)
    await session.flush()
    return _to_out(draft)
