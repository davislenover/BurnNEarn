"""Symbolic constants from SRS Appendix C that the backend uses.

Change a value here and in SRS Appendix C together, so the code and the
requirements stay the same.
"""

from datetime import timedelta
from decimal import Decimal
from enum import StrEnum


class ActivityType(StrEnum):
    """Supported activity types (SUPPORTED_ACTIVITY_TYPES)."""

    STEPS = "steps"
    WHEELCHAIR_PUSHES = "wheelchair_pushes"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    OTHER_WORKOUT = "other_workout"


# Amount of each activity type that earns one unit of virtual currency
# (u_t in SRS Section 6.7): steps, pushes, or minutes for workouts.
EARNING_RATES: dict[ActivityType, int] = {
    ActivityType.STEPS: 100,
    ActivityType.WHEELCHAIR_PUSHES: 100,
    ActivityType.CYCLING: 1,
    ActivityType.SWIMMING: 1,
    ActivityType.OTHER_WORKOUT: 1,
}

# Activity and rewards (HA SAF-7, SEC-1, SEC-20)
MAX_DAILY_CURRENCY = Decimal(300)
MAX_DAILY_STEPS = 150_000
MAX_DAILY_PUSHES = 100_000
MAX_WORKOUT_DURATION = timedelta(hours=12)
SYNC_LOOKBACK_PERIOD = timedelta(days=7)

# Simulated market (HA SEC-2, SEC-27, SEC-30)
QUOTE_CURRENCY = "USD"
QUOTE_STALENESS_LIMIT = timedelta(minutes=15)
MIN_TRADABLE_STOCKS = 50
SCENARIO_START_BALANCE = Decimal(10_000)
VALUE_TOLERANCE = Decimal("0.01")

# Accounts and data (HA SEC-17, SEC-18, SEC-37, SEC-38)
MIN_USER_AGE = 18
MIN_PASSWORD_LENGTH = 8
MAX_FAILED_SIGNINS = 5
SIGNIN_LOCKOUT_PERIOD = timedelta(minutes=15)
SESSION_TIMEOUT = timedelta(days=14)
DATA_DELETION_PERIOD = timedelta(days=30)
