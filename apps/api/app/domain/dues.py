"""The one place dues status is computed. Never stored — apps/web's own
mock types.ts already says as much: 'Derived on the server in Phase 2 from
end date + latest payment. Never stored.' Storing it would need a nightly
job and open a class of bug where the badge and the truth disagree.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

DuesStatus = Literal["paid", "soon", "due"]

# A subscription counts down to 'soon' inside this many days of its end date.
SOON_WINDOW_DAYS = 3


@dataclass(frozen=True)
class DuesInfo:
    status: DuesStatus
    owed_usd: float


def compute_dues(
    *, ends_at: datetime, plan_price_usd: float, plan_days: int, now: datetime | None = None
) -> DuesInfo:
    """A subscription that hasn't ended yet is 'paid', or 'soon' inside the
    warning window. Once it has lapsed, every full plan cycle that has
    elapsed since ends_at is another payment owed — a member who ignored
    two renewal reminders owes for two cycles, not one.
    """
    now = now or datetime.now(UTC)
    if ends_at > now:
        days_left = (ends_at - now).days
        status: DuesStatus = "soon" if days_left <= SOON_WINDOW_DAYS else "paid"
        return DuesInfo(status=status, owed_usd=0.0)

    days_overdue = (now - ends_at).days
    cycles_missed = 1 + (days_overdue // max(plan_days, 1))
    return DuesInfo(status="due", owed_usd=round(plan_price_usd * cycles_missed, 2))
