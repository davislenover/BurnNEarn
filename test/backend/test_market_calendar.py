"""Tests for the market hours."""

from datetime import datetime

import pytest

from app.market import calendar, queries
from app.market.calendar import NEW_YORK, is_market_open, is_trading_time
from app.market.providers.settings import ProviderSettings
from app.market.settings import MarketSettings, check_always_open


def new_york(*args: int) -> datetime:
    """A time in New York, such as new_york(2026, 11, 10, 10, 0)."""
    return datetime(*args, tzinfo=NEW_YORK)


@pytest.mark.parametrize(
    ("when", "is_open"),
    [
        # Tuesday Nov 10, 2026
        (new_york(2026, 11, 10, 9, 29), False),
        (new_york(2026, 11, 10, 9, 30), True),
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


def test_a_time_without_a_zone_is_refused() -> None:
    with pytest.raises(ValueError, match="time zone"):
        is_trading_time(datetime(2026, 11, 10, 10, 0))


def test_a_time_in_another_zone_is_converted_to_new_york() -> None:
    # 14:00 UTC is 9:00 in New York in November, before the open. Read as
    # 14:00 it would be open.
    when = datetime.fromisoformat("2026-11-10T14:00:00+00:00")

    assert not is_trading_time(when)


def test_always_open_opens_the_market_on_a_saturday(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saturday = new_york(2026, 11, 14, 10, 0)
    assert not is_market_open(saturday)

    always_open = MarketSettings(_env_file=None, market_always_open=True)
    monkeypatch.setattr(calendar, "get_market_settings", lambda: always_open)

    assert is_market_open(saturday)
    # Other modules ask queries, so it must answer the same.
    assert queries.is_market_open(saturday)


# Refusing always open with Finnhub is tested where the app starts, in
# test_market_poller_thread.py.
@pytest.mark.parametrize(
    ("always_open", "provider"),
    [
        (True, "fake"),
        # How the app runs in production.
        (False, "finnhub"),
    ],
)
def test_always_open_with_fake_or_finnhub_with_real_hours_is_allowed(
    always_open: bool, provider: str
) -> None:
    market = MarketSettings(_env_file=None, market_always_open=always_open)
    providers = ProviderSettings(
        _env_file=None, market_provider=provider, finnhub_api_key="not-real"
    )

    check_always_open(market, providers)
