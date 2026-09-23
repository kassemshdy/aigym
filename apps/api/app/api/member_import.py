"""Importing a gym's existing members from a spreadsheet.

Two endpoints, deliberately:

  POST /members/import/preview   a file in, normalized rows out, no writes
  POST /members/import           those rows back as JSON, all or nothing

The split exists because the manager corrects rows in between. Both call
the same functions in app/domain/csv_import.py, so what they approved in
the preview is what the commit validates — a client-side preview and a
server-side commit would be two implementations of the same rules, and
they would drift.

**The commit is all-or-nothing.** CurrentSession wraps the request in one
transaction, so raising anywhere rolls the whole thing back. A gym that
half-imported 300 members would have no way to tell which half, and
re-running would collide with the ones that did land.

**Imported members have no profile.** MemberProfile is every field a coach
fills in — height, weight, goal, injuries — and a notebook has none of it.
Inventing 170cm/70kg for 300 people would feed fabricated numbers to the
coach's screens and to the AI layer, so the profile stays absent (it is
already nullable on the read side) until a coach actually measures them.
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import CurrentSession, require_role
from app.domain.csv_import import (
    ERROR_ALREADY_A_MEMBER,
    ERROR_DUPLICATE_IN_FILE,
    ERROR_PHONE_INVALID,
    ERROR_PHONE_MISSING,
    ERROR_PLAN_UNKNOWN,
    MAX_ROWS,
    ImportRow,
    decode,
    normalize_phone,
    parse_rows,
)
from app.models import Member, Plan, Subscription
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["members"])

ManagerOrAdmin = Depends(require_role("super_admin", "manager"))

#: A 300-member gym's export is a few tens of KB. This is a guard against
#: someone uploading a video, not a real limit on any gym.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class ImportRowOut(BaseModel):
    line: int
    name: str
    name_en: str
    #: Already normalized to +961…, so the manager is approving the number
    #: that will actually be stored rather than what they typed.
    phone: str
    plan: str
    plan_id: uuid.UUID | None
    ends_at: str | None
    errors: list[str]


class ImportPreviewOut(BaseModel):
    rows: list[ImportRowOut]
    missing_columns: list[str]
    truncated: bool
    ready: int
    blocked: int


def _plan_lookup(plans: list[Plan]) -> dict[str, Plan]:
    """Plans by name, in both languages and case-folded — a spreadsheet
    says "monthly" or "شهري", not a UUID."""
    table: dict[str, Plan] = {}
    for plan in plans:
        for value in plan.name.values():
            if isinstance(value, str) and value.strip():
                table.setdefault(value.strip().casefold(), plan)
    return table


async def _resolve(
    session: CurrentSession,
    rows: list[ImportRow],
    default_plan_id: uuid.UUID | None,
) -> tuple[list[ImportRowOut], dict[int, Plan]]:
    """Attach the two errors the pure module cannot know about: a plan name
    this gym does not have, and a phone already on the roster."""
    plans = list((await session.execute(select(Plan))).scalars())
    by_name = _plan_lookup(plans)
    by_id = {p.id: p for p in plans}
    fallback = by_id.get(default_plan_id) if default_plan_id else None

    existing = set(
        (await session.execute(select(Member.phone))).scalars().all()
    )

    out: list[ImportRowOut] = []
    resolved: dict[int, Plan] = {}
    for row in rows:
        errors = list(row.errors)
        plan = by_name.get(row.plan.strip().casefold()) if row.plan.strip() else fallback
        if plan is None:
            errors.append(ERROR_PLAN_UNKNOWN)
        if row.phone and row.phone in existing:
            errors.append(ERROR_ALREADY_A_MEMBER)

        if plan is not None:
            resolved[row.line] = plan
        out.append(
            ImportRowOut(
                line=row.line,
                name=row.name,
                name_en=row.name_en,
                phone=row.phone,
                plan=row.plan,
                plan_id=plan.id if plan else None,
                ends_at=row.ends_at.isoformat() if row.ends_at else None,
                errors=errors,
            )
        )
    return out, resolved


@router.post("/members/import/preview", response_model=ImportPreviewOut)
async def preview_member_import(
    session: CurrentSession,
    file: Annotated[UploadFile, File()],
    default_plan_id: uuid.UUID | None = None,
    _claims: AccessTokenClaims = ManagerOrAdmin,
) -> ImportPreviewOut:
    """Writes nothing. Every row comes back normalized and, where it cannot
    be imported, carrying stable error keys the client renders in the
    manager's own language."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That file is too big to be a member list"
        )

    parsed = parse_rows(decode(raw))
    rows, _ = await _resolve(session, parsed.rows, default_plan_id)
    return ImportPreviewOut(
        rows=rows,
        missing_columns=parsed.missing_columns,
        truncated=parsed.truncated,
        ready=sum(1 for r in rows if not r.errors),
        blocked=sum(1 for r in rows if r.errors),
    )


class CommitRow(BaseModel):
    line: int
    name: Annotated[str, Field(min_length=1, max_length=120)]
    name_en: Annotated[str, Field(min_length=1, max_length=120)]
    phone: Annotated[str, Field(min_length=1, max_length=32)]
    plan_id: uuid.UUID
    ends_at: str | None = None


class CommitImportRequest(BaseModel):
    rows: Annotated[list[CommitRow], Field(min_length=1, max_length=MAX_ROWS)]


class CommitImportOut(BaseModel):
    imported: int


def _period_end(ends_at: str | None, started: datetime, plan: Plan) -> datetime:
    """An existing member keeps the end date the gym already promised them.

    This is the whole reason the importer reads a date at all: without it
    every imported member looks like they joined today, and the dues and
    collection figures are wrong from the first day the gym uses the
    product — which is the one number it is sold on.
    """
    if ends_at:
        try:
            parsed = datetime.fromisoformat(ends_at)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"Bad end date: {ends_at}"
            ) from exc
        if parsed.tzinfo is None:
            parsed = datetime.combine(parsed.date(), time(0, 0), tzinfo=UTC)
        return parsed
    return started + timedelta(days=plan.days)


@router.post(
    "/members/import", response_model=CommitImportOut, status_code=status.HTTP_201_CREATED
)
async def commit_member_import(
    body: CommitImportRequest,
    session: CurrentSession,
    claims: AccessTokenClaims = ManagerOrAdmin,
) -> CommitImportOut:
    """All of them or none of them. Every check below raises, and the
    request's single transaction takes the whole batch back with it."""
    plans = {
        p.id: p for p in (await session.execute(select(Plan))).scalars()
    }
    existing = set((await session.execute(select(Member.phone))).scalars().all())

    seen: set[str] = set()
    now = datetime.now(UTC)

    for row in body.rows:
        phone = normalize_phone(row.phone)
        if phone is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Line {row.line}: {ERROR_PHONE_INVALID if row.phone else ERROR_PHONE_MISSING}",
            )
        if phone in seen:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Line {row.line}: {ERROR_DUPLICATE_IN_FILE}",
            )
        if phone in existing:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Line {row.line}: {ERROR_ALREADY_A_MEMBER}"
            )
        plan = plans.get(row.plan_id)
        if plan is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Line {row.line}: {ERROR_PLAN_UNKNOWN}",
            )
        seen.add(phone)

        member = Member(
            id=uuid.uuid4(), gym_id=claims.gym_id, name=row.name.strip(),
            name_en=row.name_en.strip(), phone=phone, joined_at=now,
        )
        session.add(member)
        # No relationship() anywhere in app/models, so the unit of work
        # cannot order a subscription after the member it references.
        await session.flush()

        session.add(
            Subscription(
                id=uuid.uuid4(), gym_id=claims.gym_id, member_id=member.id, plan_id=plan.id,
                starts_at=now, ends_at=_period_end(row.ends_at, now, plan),
            )
        )

    await session.flush()
    return CommitImportOut(imported=len(body.rows))
