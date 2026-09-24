"""The owner dashboard's numbers — the ones docs/GTM.md's conditional
guarantee is settled on ("if it does not recover more in missed dues than
we charge you in the first 90 days, you do not pay").

Every figure is reported against the preceding window of equal length,
because the guarantee is a before/after claim and a single number proves
nothing on its own.

This module does the fetching; app/domain/analytics.py does the arithmetic.
The reads are deliberately bulk and bounded by the *window*, not by member
count — a gym with 300 members runs the same handful of queries as one with
30, which is the same rule GET /members was fixed to follow.

**A known limitation, stated rather than hidden:** there is no way to mark
a member as having left (members has no status column and nothing deletes
one). So `lapsed` counts anyone without a recent visit, including people who
quit months ago, and their final unrenewed period keeps counting as
uncollected. Both figures therefore drift upward over time. Adding a member
lifecycle is the fix; until then these read as "quiet or gone" rather than
"quiet", and a gym owner reading them should know which.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentSession, require_role
from app.domain.analytics import (
    CollectionStats,
    SubscriptionRow,
    bucket_by_week,
    collection_stats,
    lapsed_count_as_of,
    renewal_outcomes,
    week_starts,
)
from app.models import Attendance, Member, Subscription
from app.security.jwt import AccessTokenClaims

router = APIRouter(tags=["analytics"])

# super_admin is listed explicitly: roles are flat, not a hierarchy, so
# leaving it out would lock the gym owner out of their own dashboard and
# look exactly like a correct 403 (app/deps.py's require_role docstring).
ManagerOrAdmin = Depends(require_role("super_admin", "manager"))

#: Matches GET /members/lapsed's default, so the dashboard and the list a
#: manager clicks through to can never disagree.
LAPSED_AFTER_DAYS = 14

DEFAULT_WEEKS = 12


class WindowOut(BaseModel):
    due_count: int
    on_time_count: int
    #: None when nothing fell due — distinct from 0.0, which means every
    #: renewal in the window was missed.
    on_time_rate: float | None
    collected_usd: float
    uncollected_usd: float


class SeriesPointOut(BaseModel):
    week_start: date
    on_time_rate: float | None
    collected_usd: float


class AnalyticsSummaryOut(BaseModel):
    weeks: int
    window_start: date
    previous_start: date
    collection: WindowOut
    collection_previous: WindowOut
    lapsed_now: int
    lapsed_at_window_start: int
    new_members: int
    new_members_previous: int
    active_members: int
    #: Members marked as having left inside the window, and inside the one
    #: before it. The other half of "stop losing members quietly": until
    #: decision 43 there was no way to count a departure at all, only to
    #: watch the lapsed list grow.
    left_members: int
    left_members_previous: int
    series: list[SeriesPointOut]


def _to_out(stats: CollectionStats) -> WindowOut:
    return WindowOut(
        due_count=stats.due_count,
        on_time_count=stats.on_time_count,
        on_time_rate=stats.on_time_rate,
        collected_usd=stats.collected_usd,
        uncollected_usd=stats.uncollected_usd,
    )


async def _last_visits_on_or_before(
    session: AsyncSession, cutoff: date
) -> dict[uuid.UUID, date]:
    """Each member's most recent attendance at or before `cutoff`. One
    GROUP BY — asking this per member is what made the old lapsed endpoint
    O(members) queries."""
    result = await session.execute(
        select(Attendance.member_id, func.max(Attendance.date))
        .where(Attendance.date <= cutoff)
        .group_by(Attendance.member_id)
    )
    return {member_id: last for member_id, last in result.all()}


@router.get("/analytics/summary", response_model=AnalyticsSummaryOut)
async def analytics_summary(
    session: CurrentSession,
    weeks: Annotated[int, Query(ge=1, le=52)] = DEFAULT_WEEKS,
    _claims: AccessTokenClaims = ManagerOrAdmin,
) -> AnalyticsSummaryOut:
    now = datetime.now(UTC)
    today = now.date()
    span = timedelta(weeks=weeks)
    window_start = now - span
    previous_start = window_start - span

    # One read covering both windows: everything that fell due since the
    # previous window opened.
    # No join to plans any more: the price a period was sold at lives on
    # the period. That is not only cheaper — joining to plans is what made
    # a price edit rewrite history, which is the whole of decision 42.
    due_rows = (
        await session.execute(
            select(Subscription).where(
                Subscription.ends_at >= previous_start, Subscription.ends_at <= now
            )
        )
    ).scalars().all()
    due = [
        SubscriptionRow(
            member_id=sub.member_id, starts_at=sub.starts_at, ends_at=sub.ends_at,
            plan_price_usd=float(sub.price_usd),
        )
        for sub in due_rows
    ]

    # Every subscription belonging to those members, so a renewal that
    # landed after the window still counts as collected. Bounded by the
    # members who had something fall due, not by the whole roster.
    by_member: dict[uuid.UUID, list[SubscriptionRow]] = {}
    member_ids = {row.member_id for row in due}
    if member_ids:
        all_rows = (
            await session.execute(
                select(Subscription).where(Subscription.member_id.in_(member_ids))
            )
        ).scalars().all()
        for sub in all_rows:
            by_member.setdefault(sub.member_id, []).append(
                SubscriptionRow(
                    member_id=sub.member_id, starts_at=sub.starts_at, ends_at=sub.ends_at,
                    plan_price_usd=float(sub.price_usd),
                )
            )

    outcomes = renewal_outcomes(due=due, by_member=by_member)
    current = [o for o in outcomes if o.due_at >= window_start]
    previous = [o for o in outcomes if o.due_at < window_start]

    # Everyone, including leavers: the counts below need both, and asking
    # twice would be a second round trip for the same rows.
    everyone = list((await session.execute(select(Member))).scalars())
    # Roster counts — active only. A member who quit must stop inflating
    # "lapsed" and "active", which is the drift decision 43 exists to stop.
    members = [m for m in everyone if m.status == "active"]
    all_ids = [m.id for m in members]
    joined_before_window = [m.id for m in members if m.joined_at < window_start]
    departures = [m.left_at for m in everyone if m.left_at is not None]

    visits_now = await _last_visits_on_or_before(session, today)
    visits_then = await _last_visits_on_or_before(session, window_start.date())

    series_starts = week_starts(end=today, weeks=weeks)
    buckets = bucket_by_week(outcomes=current, starts=series_starts)

    return AnalyticsSummaryOut(
        weeks=weeks,
        window_start=window_start.date(),
        previous_start=previous_start.date(),
        collection=_to_out(collection_stats(current)),
        collection_previous=_to_out(collection_stats(previous)),
        lapsed_now=lapsed_count_as_of(
            member_ids=all_ids, last_visit_before=visits_now,
            as_of=today, min_days=LAPSED_AFTER_DAYS,
        ),
        # Only members who had already joined — counting today's roster
        # against a date before they existed would invent churn.
        lapsed_at_window_start=lapsed_count_as_of(
            member_ids=joined_before_window, last_visit_before=visits_then,
            as_of=window_start.date(), min_days=LAPSED_AFTER_DAYS,
        ),
        new_members=sum(1 for m in members if m.joined_at >= window_start),
        new_members_previous=sum(
            1 for m in members if previous_start <= m.joined_at < window_start
        ),
        active_members=len(members),
        left_members=sum(1 for at in departures if at >= window_start),
        left_members_previous=sum(
            1 for at in departures if previous_start <= at < window_start
        ),
        series=[
            SeriesPointOut(
                week_start=start,
                on_time_rate=stats.on_time_rate,
                collected_usd=stats.collected_usd,
            )
            for start, stats in zip(series_starts, buckets, strict=True)
        ],
    )
