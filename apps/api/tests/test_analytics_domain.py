"""Pure-function tests for app/domain/analytics.py — no database, no HTTP.

These assert arithmetic that the sales guarantee is settled on, so the
expected values here are worked out by hand rather than read back from the
implementation.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from app.domain.analytics import (
    ON_TIME_DAYS,
    RenewalOutcome,
    SubscriptionRow,
    bucket_by_week,
    collection_stats,
    lapsed_count_as_of,
    renewal_outcomes,
    week_starts,
)

DUE = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _member() -> uuid.UUID:
    return uuid.uuid4()


def _period(member_id: uuid.UUID, *, starts: datetime, ends: datetime, price: float = 30.0):
    return SubscriptionRow(
        member_id=member_id, starts_at=starts, ends_at=ends, plan_price_usd=price
    )


def _outcomes_for(renewal_offset_days: int | None, price: float = 30.0):
    """One member, one period ending at DUE, renewed `renewal_offset_days`
    after the due date (None = never renewed)."""
    member_id = _member()
    period = _period(member_id, starts=DUE - timedelta(days=30), ends=DUE, price=price)
    subs = [period]
    if renewal_offset_days is not None:
        subs.append(
            _period(
                member_id,
                starts=DUE + timedelta(days=renewal_offset_days),
                ends=DUE + timedelta(days=renewal_offset_days + 30),
                price=price,
            )
        )
    return renewal_outcomes(due=[period], by_member={member_id: subs})


def test_paid_early_reads_as_zero_days_late() -> None:
    # Paying early makes record_payment start the renewal at the previous
    # end date exactly, so the gap is 0 rather than negative.
    (outcome,) = _outcomes_for(0)
    assert outcome.days_late == 0
    assert outcome.on_time
    assert outcome.collected


def test_paid_on_the_last_on_time_day_still_counts() -> None:
    (outcome,) = _outcomes_for(ON_TIME_DAYS)
    assert outcome.days_late == 7
    assert outcome.on_time


def test_paid_one_day_past_the_window_does_not_count() -> None:
    (outcome,) = _outcomes_for(ON_TIME_DAYS + 1)
    assert outcome.days_late == 8
    assert not outcome.on_time
    # Late is still collected — it is money in, just not on time.
    assert outcome.collected


def test_never_renewed_is_uncollected() -> None:
    (outcome,) = _outcomes_for(None)
    assert outcome.days_late is None
    assert not outcome.on_time
    assert not outcome.collected


def test_a_zero_length_period_is_never_its_own_renewal() -> None:
    """For an ordinary period `starts_at < ends_at`, so the `starts_at >=
    ends_at` filter already rules it out. The one shape that can match
    itself is a zero-length period — and the rows are passed here as
    equal-but-distinct instances on purpose, because the caller builds
    `due` and `by_member` separately. Excluding by object identity would
    let this count as renewed at 0 days late, pinning the on-time rate at
    100% for good.
    """
    member_id = _member()
    in_due = _period(member_id, starts=DUE, ends=DUE)
    same_row_different_object = _period(member_id, starts=DUE, ends=DUE)
    assert in_due is not same_row_different_object
    assert in_due == same_row_different_object

    (outcome,) = renewal_outcomes(
        due=[in_due], by_member={member_id: [same_row_different_object]}
    )
    assert outcome.days_late is None, "a period counted itself as its own renewal"


def test_the_earliest_renewal_wins_when_a_member_has_several() -> None:
    member_id = _member()
    period = _period(member_id, starts=DUE - timedelta(days=30), ends=DUE)
    later = _period(member_id, starts=DUE + timedelta(days=40), ends=DUE + timedelta(days=70))
    nearer = _period(member_id, starts=DUE + timedelta(days=2), ends=DUE + timedelta(days=32))
    (outcome,) = renewal_outcomes(
        due=[period], by_member={member_id: [period, later, nearer]}
    )
    assert outcome.days_late == 2


def test_collection_stats_sums_money_by_whether_it_arrived() -> None:
    outcomes = [
        *_outcomes_for(1, price=30.0),
        *_outcomes_for(20, price=80.0),
        *_outcomes_for(None, price=280.0),
    ]
    stats = collection_stats(outcomes)
    assert stats.due_count == 3
    assert stats.on_time_count == 1
    assert stats.collected_usd == 110.0
    assert stats.uncollected_usd == 280.0
    assert stats.on_time_rate == round(1 / 3, 4)


def test_on_time_rate_is_none_rather_than_zero_when_nothing_was_due() -> None:
    stats = collection_stats([])
    assert stats.due_count == 0
    assert stats.on_time_rate is None


def test_lapsed_counts_a_member_who_never_visited() -> None:
    a, b, c = _member(), _member(), _member()
    as_of = date(2026, 6, 30)
    count = lapsed_count_as_of(
        member_ids=[a, b, c],
        last_visit_before={
            a: as_of - timedelta(days=13),  # still active
            b: as_of - timedelta(days=14),  # exactly at the threshold
            # c never visited
        },
        as_of=as_of,
        min_days=14,
    )
    assert count == 2


def test_week_starts_are_mondays_oldest_first() -> None:
    # 2026-06-30 is a Tuesday; its Monday is the 29th.
    starts = week_starts(end=date(2026, 6, 30), weeks=3)
    assert starts == [date(2026, 6, 15), date(2026, 6, 22), date(2026, 6, 29)]
    assert all(s.weekday() == 0 for s in starts)


def test_bucketing_drops_outcomes_older_than_the_window() -> None:
    starts = week_starts(end=date(2026, 6, 30), weeks=2)  # 22nd, 29th
    member_id = _member()
    in_last = RenewalOutcome(
        member_id=member_id,
        due_at=datetime(2026, 6, 30, tzinfo=UTC),
        days_late=1,
        amount_usd=30.0,
    )
    too_old = RenewalOutcome(
        member_id=member_id,
        due_at=datetime(2026, 5, 1, tzinfo=UTC),
        days_late=1,
        amount_usd=99.0,
    )
    buckets = bucket_by_week(outcomes=[in_last, too_old], starts=starts)
    assert [b.due_count for b in buckets] == [0, 1]
    # The old one is dropped, not folded into the first bucket.
    assert buckets[0].collected_usd == 0.0
    assert buckets[1].collected_usd == 30.0
