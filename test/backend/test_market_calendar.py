"""Tests for the market hours."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.market import calendar
from app.market.calendar import NEW_YORK, is_market_open, is_trading_time
from app.market.settings import MarketSettings


def new_york(*args: int) -> datetime:
    """A time in New York, such as new_york(2026, 11, 10, 10, 0)."""
    return datetime(*args, tzinfo=NEW_YORK)


@pytest.mark.parametrize(
    ("when", "is_open"),
    [
        # Tuesday Nov 10, 2026
        (new_york(2026, 11, 10, 9, 29), False),
        (new_york(2026, 11, 10, 9, 30), True),
        (new_york(2026, 11, 10, 10, 0), True),
        (new_york(2026, 11, 10, 15, 59), True),
        (new_york(2026, 11, 10, 16, 0), False),
        # Saturday Nov 14
        (new_york(2026, 11, 14, 10, 0), False),
        # Thanksgiving, Thursday Nov 26
        (new_york(2026, 11, 26, 10, 0), False),
        # The day after Thanksgiving closes at 13:00
        (new_york(2026, 11, 27, 12, 59), True),
        (new_york(2026, 11, 27, 13, 0), False),
    ],
)
def test_the_exchanges_hours(when: datetime, is_open: bool) -> None:
    assert is_trading_time(when) is is_open


def test_a_time_in_another_zone_is_converted_to_new_york() -> None:
    # 15:00 UTC is 10:00 in New York in November.
    when = datetime.fromisoformat("2026-11-10T15:00:00+00:00")

    assert is_trading_time(when)


def test_the_market_is_open_at_its_real_hours_by_default() -> None:
    assert is_market_open(new_york(2026, 11, 10, 10, 0))
    assert not is_market_open(new_york(2026, 11, 14, 10, 0))


def test_always_open_opens_the_market_on_a_saturday(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    always_open = MarketSettings(_env_file=None, market_always_open=True)
    monkeypatch.setattr(calendar, "get_market_settings", lambda: always_open)

    assert is_market_open(new_york(2026, 11, 14, 10, 0))


def test_always_open_is_refused_with_finnhub() -> None:
    with pytest.raises(ValidationError, match="MARKET_ALWAYS_OPEN"):
        MarketSettings(
            _env_file=None,
            market_provider="finnhub",
            finnhub_api_key="not-real",
            market_always_open=True,
        )
