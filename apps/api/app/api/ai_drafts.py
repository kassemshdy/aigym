"""The coach's AI draft inbox (decision 10): nothing an assistant or a
coach's "generate" button proposes ever reaches a member's program or
calorie target directly — it lands here, pending, until a coach approves
it. One mechanism for both origins (decision 31) — see app/api/chat.py
(stage 7) and app/api/ai_drafts.py's generate route (stage 9) for the two
producers; this file is the single consumer both write into.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentSession, require_role
from app.domain.ai_drafts import CalorieTargetUpdate, ProgramExerciseUpdate, apply_draft
from app.models import AiPlanDraft, Exercise, Member, MemberProfile, MemberProgram, ProgramExercise
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["ai-drafts"])

ManagerOrCoach = Depends(require_role("super_admin", "manager", "coach"))


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
