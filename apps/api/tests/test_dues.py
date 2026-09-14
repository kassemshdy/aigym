from datetime import UTC, datetime, timedelta

from app.domain.dues import compute_dues

NOW = datetime(2026, 9, 14, tzinfo=UTC)


def test_far_future_end_date_is_paid() -> None:
    dues = compute_dues(
        ends_at=NOW + timedelta(days=30), plan_price_usd=35, plan_days=30, now=NOW
    )
    assert dues.status == "paid"
    assert dues.owed_usd == 0.0


def test_inside_soon_window_is_soon() -> None:
    dues = compute_dues(
        ends_at=NOW + timedelta(days=2), plan_price_usd=35, plan_days=30, now=NOW
    )
    assert dues.status == "soon"
    assert dues.owed_usd == 0.0


def test_just_lapsed_owes_one_cycle() -> None:
    dues = compute_dues(
        ends_at=NOW - timedelta(days=1), plan_price_usd=35, plan_days=30, now=NOW
    )
    assert dues.status == "due"
    assert dues.owed_usd == 35.0


def test_two_cycles_lapsed_owes_double() -> None:
    dues = compute_dues(
        ends_at=NOW - timedelta(days=31), plan_price_usd=35, plan_days=30, now=NOW
    )
    assert dues.status == "due"
    assert dues.owed_usd == 70.0


def test_ends_exactly_now_is_due() -> None:
    dues = compute_dues(ends_at=NOW, plan_price_usd=35, plan_days=30, now=NOW)
    assert dues.status == "due"
    assert dues.owed_usd == 35.0
