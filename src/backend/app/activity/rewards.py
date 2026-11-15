"""Step reward rules. These need no database or current clock."""

from datetime import date, timedelta
from decimal import Decimal

from app.core.constants import (
    EARNING_RATES,
    MAX_DAILY_CURRENCY,
    MAX_DAILY_STEPS,
    SYNC_LOOKBACK_PERIOD,
    ActivityType,
)


def daily_reward(step_count: int) -> Decimal:
    """Currency earned by a validated daily total (FR_ActEarn)."""
    if step_count > MAX_DAILY_STEPS:
        return Decimal(0)
    return min(
        Decimal(step_count // EARNING_RATES[ActivityType.STEPS]),
        MAX_DAILY_CURRENCY,
    )


def top_up(reward: Decimal, already_paid: Decimal) -> Decimal:
    """What is still owed. A lower total never takes currency back."""
    return max(reward - already_paid, Decimal(0))


def allowed_dates(today: date) -> frozenset[date]:
    """Today and the preceding six days (SEC-20)."""
    return frozenset(
        today - timedelta(days=offset)
        for offset in range(SYNC_LOOKBACK_PERIOD.days)
    )
