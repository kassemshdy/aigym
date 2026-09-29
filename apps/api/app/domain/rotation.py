"""Which day of a multi-day plan comes next. Pure. Decision 53.

A plan's days repeat in order — Push, Pull, Legs, Push — rather than being
pinned to weekdays, because members miss days: someone who trained Push on
Monday and comes back on Thursday is due Pull, not whatever Thursday says.
"""


def next_day(day_count: int, last_day: int | None) -> int:
    """The day after `last_day`, wrapping round. Day 0 for a one-day plan,
    for a member who has not trained this plan yet, and for a last day the
    plan no longer has (a coach removed days since)."""
    if day_count <= 1 or last_day is None or not 0 <= last_day < day_count:
        return 0
    return (last_day + 1) % day_count
