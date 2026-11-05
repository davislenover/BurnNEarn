"""When the New York Stock Exchange is open."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.market.settings import get_market_settings

NEW_YORK = ZoneInfo("America/New_York")
OPENS_AT = time(9, 30)
CLOSES_AT = time(16, 0)
EARLY_CLOSE_AT = time(13, 0)

# NYSE holidays (https://www.nyse.com/markets/hours-calendars). Add the next
# year's dates each December.
HOLIDAYS = {
    # 2026
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
    # 2027
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),
    date(2027, 5, 31),
    date(2027, 6, 18),
    date(2027, 7, 5),
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24),
}

# Days the market closes at 13:00 instead of 16:00.
EARLY_CLOSES = {
    date(2026, 11, 27),
    date(2026, 12, 24),
    date(2027, 11, 26),
}


def is_trading_time(now: datetime) -> bool:
    """Whether the exchange is open at now, by its real hours.

    now must have a time zone. It is converted to New York time, so daylight
    saving time is handled.
    """
    if now.tzinfo is None:
        # Without a zone, Python would assume the computer's own zone, so
        # the answer would differ between CI and a laptop.
        raise ValueError("now must have a time zone")
    local = now.astimezone(NEW_YORK)
    day = local.date()
    if local.weekday() >= 5 or day in HOLIDAYS:
        return False
    closes_at = EARLY_CLOSE_AT if day in EARLY_CLOSES else CLOSES_AT
    return OPENS_AT <= local.time() < closes_at


def is_market_open(now: datetime) -> bool:
    """Whether the app treats the market as open at now.

    This is the exchange's real hours, unless MARKET_ALWAYS_OPEN is on for
    development in the evening.
    """
    return get_market_settings().market_always_open or is_trading_time(now)
