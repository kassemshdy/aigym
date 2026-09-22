"""The numbers the sales guarantee is settled on (docs/GTM.md): "if it does
not recover more in missed dues than we charge you in the first 90 days,
you do not pay." Pure — the caller fetches rows and hands them in, same
convention as dues.py/workout.py/guardrails.py.

**Why this does not contradict decision 17 (dues computed, never stored).**
It asks a different question. `compute_dues()` answers "what does this
member owe *right now*"; this answers "did renewals historically get paid
promptly." Nothing here is stored, and no dues arithmetic is restated in
SQL.

**How a renewal's timing is known without looking at payments at all.**
`record_payment` (app/api/members.py) writes the renewal subscription with
`starts_at = max(previous.ends_at, now)`. So the renewal's own start date
already encodes when it was paid, relative to the due date:

- paid early → `starts_at == previous.ends_at`, so days_late is 0
- paid late  → `starts_at == the moment of payment`, so days_late is exact

That makes the payments table unnecessary for this metric, which removes a
whole class of mistake — matching a payment row to the period it paid for
is guesswork once a member pays twice in a month, and this is not.

A member's first subscription comes from `create_member`, not a renewal,
so it is a join rather than a collection event and is only ever counted as
a *due date* once it ends.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# A renewal counts as collected on time if it landed within this many days
# of the due date. GTM's number is 7; it lives here rather than at a call
# site so the dashboard and any future report cannot disagree about it.
ON_TIME_DAYS = 7


@dataclass(frozen=True)
class SubscriptionRow:
    """One membership period, with its plan's price already resolved."""

    member_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    plan_price_usd: float


@dataclass(frozen=True)
class RenewalOutcome:
    member_id: uuid.UUID
    due_at: datetime
    #: None when the member never renewed after this period ended.
    days_late: int | None
    amount_usd: float

    @property
    def collected(self) -> bool:
        return self.days_late is not None

    @property
    def on_time(self) -> bool:
        return self.days_late is not None and self.days_late <= ON_TIME_DAYS


@dataclass(frozen=True)
class CollectionStats:
    due_count: int
    on_time_count: int
    collected_usd: float
    uncollected_usd: float

    @property
    def on_time_rate(self) -> float | None:
        """None, not zero, when nothing fell due in the window — "no
        renewals were due" and "every renewal was missed" are different
        facts and a dashboard that shows 0% for both is lying."""
        if self.due_count == 0:
            return None
        return round(self.on_time_count / self.due_count, 4)


def renewal_outcomes(
    *, due: list[SubscriptionRow], by_member: dict[uuid.UUID, list[SubscriptionRow]]
) -> list[RenewalOutcome]:
    """For each period that fell due, how late its renewal was.

    `by_member` must hold every subscription for the members in `due`,
    including ones starting after the window, or a renewal paid just past
    the window edge would be miscounted as never collected.
    """
    outcomes = []
    for period in due:
        # Self-exclusion compares values, not object identity: the caller
        # may well build `due` and `by_member` as separate instances of
        # equal rows, and an `is not` check would then let a period count
        # as its own renewal — which reads as 0 days late and would peg the
        # on-time rate at 100% forever.
        candidates = [
            s.starts_at
            for s in by_member.get(period.member_id, ())
            if s.starts_at >= period.ends_at
            and (s.starts_at, s.ends_at) != (period.starts_at, period.ends_at)
        ]
        renewed_at = min(candidates) if candidates else None
        outcomes.append(
            RenewalOutcome(
                member_id=period.member_id,
                due_at=period.ends_at,
                days_late=(renewed_at - period.ends_at).days if renewed_at else None,
                amount_usd=period.plan_price_usd,
            )
        )
    return outcomes


def collection_stats(outcomes: list[RenewalOutcome]) -> CollectionStats:
    return CollectionStats(
        due_count=len(outcomes),
        on_time_count=sum(1 for o in outcomes if o.on_time),
        collected_usd=round(sum(o.amount_usd for o in outcomes if o.collected), 2),
        uncollected_usd=round(sum(o.amount_usd for o in outcomes if not o.collected), 2),
    )


def lapsed_count_as_of(
    *,
    member_ids: list[uuid.UUID],
    last_visit_before: dict[uuid.UUID, date],
    as_of: date,
    min_days: int,
) -> int:
    """How many of these members had gone `min_days` without a visit as of
    `as_of`. `last_visit_before` is each member's most recent attendance on
    or before that date — a member with no entry never visited, which
    counts as lapsed, matching GET /members/lapsed.
    """
    lapsed = 0
    for member_id in member_ids:
        last = last_visit_before.get(member_id)
        if last is None or (as_of - last).days >= min_days:
            lapsed += 1
    return lapsed


def week_starts(*, end: date, weeks: int) -> list[date]:
    """The Monday of each of the last `weeks` weeks, oldest first. Buckets
    are computed server-side so the client renders a series without doing
    any date arithmetic of its own."""
    this_monday = end - timedelta(days=end.weekday())
    return [this_monday - timedelta(weeks=offset) for offset in range(weeks - 1, -1, -1)]


def bucket_by_week(
    *, outcomes: list[RenewalOutcome], starts: list[date]
) -> list[CollectionStats]:
    """One CollectionStats per week in `starts`. An outcome falls in the
    latest bucket whose start is on or before its due date; anything older
    than the first bucket is dropped rather than silently piled into it."""
    buckets: list[list[RenewalOutcome]] = [[] for _ in starts]
    for outcome in outcomes:
        due_day = outcome.due_at.date()
        index = None
        for i, start in enumerate(starts):
            if due_day >= start:
                index = i
        if index is not None:
            buckets[index].append(outcome)
    return [collection_stats(b) for b in buckets]
