"""Tests for the poller thread: when it polls, and how the app starts and
stops it."""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.plugins import ModuleHealth
from app.main import create_app
from app.market import poller
from app.market.calendar import NEW_YORK
from app.market.models import Price
from app.market.plugin import PLUGIN
from app.market.poller import run_poller, should_poll
from app.market.providers.base import MarketDataError, Quote
from app.market.providers.settings import get_provider_settings
from app.market.settings import MarketSettings


def new_york(*args: int) -> datetime:
    return datetime(*args, tzinfo=NEW_YORK)


OPEN = new_york(2026, 11, 10, 10, 0)
SATURDAY = new_york(2026, 11, 14, 10, 0)


class CountingProvider:
    """Answers every symbol with the same price, and counts the calls."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls = 0
        self.error = error

    def get_quote(self, symbol: str) -> Quote:
        self.calls += 1
        if self.error:
            raise self.error
        return Quote(symbol=symbol, price=Decimal("100"), quoted_at=OPEN)


@pytest.fixture(autouse=True)
def fresh_poller_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test from a new poller status, so no test sees what
    another one left behind."""
    monkeypatch.setattr(poller, "_status", poller._Status())


def stopped() -> threading.Event:
    """A stop signal that is already set, so run_poller polls once."""
    stop = threading.Event()
    stop.set()
    return stop


@pytest.mark.parametrize(
    ("when", "polls"),
    [
        (new_york(2026, 11, 10, 9, 29), False),
        (new_york(2026, 11, 10, 9, 30), True),
        # For 15 minutes after the close, for the official closing price
        (new_york(2026, 11, 10, 16, 14), True),
        (new_york(2026, 11, 10, 16, 15), False),
        # The day after Thanksgiving closes at 13:00
        (new_york(2026, 11, 27, 13, 14), True),
        (new_york(2026, 11, 27, 13, 15), False),
        (SATURDAY, False),
    ],
)
def test_when_the_poller_polls(when: datetime, polls: bool) -> None:
    assert should_poll(when) is polls


@pytest.fixture
def test_sessions(db_session: Session):
    """A session factory for run_poller that hands it the test's session,
    so whatever it commits is undone when the test ends."""

    @contextmanager
    def factory() -> Iterator[Session]:
        yield db_session

    return factory


def test_one_run_saves_a_price_for_each_asset(
    db_session: Session, test_sessions
) -> None:
    provider = CountingProvider()

    run_poller(stopped(), provider, lambda: OPEN, test_sessions)

    saved = db_session.scalar(select(func.count()).select_from(Price))
    assert saved == provider.calls > 0


def test_nothing_is_asked_while_the_market_is_closed(test_sessions) -> None:
    provider = CountingProvider()

    run_poller(stopped(), provider, lambda: SATURDAY, test_sessions)

    assert provider.calls == 0


def test_an_unexpected_error_does_not_stop_the_poller(
    test_sessions,
) -> None:
    provider = CountingProvider(error=RuntimeError("bug"))

    # Logs the error and returns normally instead of raising.
    run_poller(stopped(), provider, lambda: OPEN, test_sessions)

    assert provider.calls == 1


def use_settings(monkeypatch: pytest.MonkeyPatch, **values: object) -> None:
    settings = MarketSettings(_env_file=None, **values)
    monkeypatch.setattr(poller, "get_market_settings", lambda: settings)


def test_the_app_starts_and_stops_the_poller_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, market_poller_enabled=True)
    started = threading.Event()
    finished = threading.Event()

    def fake_run_poller(stop: threading.Event, provider: object) -> None:
        started.set()
        stop.wait()
        finished.set()

    monkeypatch.setattr(poller, "run_poller", fake_run_poller)

    with TestClient(create_app([PLUGIN])):
        assert started.wait(5)
        assert not finished.is_set()

    assert finished.is_set()


def test_the_app_does_not_start_the_poller_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, market_poller_enabled=False)
    started = threading.Event()
    monkeypatch.setattr(poller, "run_poller", lambda *args: started.set())

    with TestClient(create_app([PLUGIN])):
        pass

    assert not started.is_set()


def test_bad_market_settings_stop_the_app_from_starting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MARKET_PROVIDER", "finnhub")
    monkeypatch.setenv("FINNHUB_API_KEY", "")
    get_provider_settings.cache_clear()
    try:
        with (
            pytest.raises(ValidationError),
            TestClient(create_app([PLUGIN])),
        ):
            pass
    finally:
        get_provider_settings.cache_clear()


def test_always_open_with_finnhub_stops_the_app_from_starting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, market_always_open=True)
    monkeypatch.setenv("MARKET_PROVIDER", "finnhub")
    monkeypatch.setenv("FINNHUB_API_KEY", "not-real")
    get_provider_settings.cache_clear()
    try:
        with (
            pytest.raises(ValueError, match="MARKET_ALWAYS_OPEN"),
            TestClient(create_app([PLUGIN])),
        ):
            pass
    finally:
        get_provider_settings.cache_clear()


def test_a_poll_that_misses_a_price_is_a_failed_poll(test_sessions) -> None:
    run_poller(
        stopped(),
        CountingProvider(MarketDataError("down")),
        lambda: OPEN,
        test_sessions,
    )
    assert poller._status.last_poll_failed is True

    # It stays while the market is closed and nothing is polled.
    run_poller(stopped(), CountingProvider(), lambda: SATURDAY, test_sessions)
    assert poller._status.last_poll_failed is True

    # The next poll that saves every price clears it.
    run_poller(stopped(), CountingProvider(), lambda: OPEN, test_sessions)
    assert poller._status.last_poll_failed is False


def test_a_poll_that_raises_is_a_failed_poll(test_sessions) -> None:
    run_poller(
        stopped(),
        CountingProvider(RuntimeError("bug")),
        lambda: OPEN,
        test_sessions,
    )

    assert poller._status.last_poll_failed is True


def wait_for(condition: Callable[[], bool]) -> bool:
    """Wait up to 5 seconds for condition, which another thread changes."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_health_says_off_when_the_poller_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, market_poller_enabled=False)

    with TestClient(create_app([PLUGIN])):
        assert poller.health() == ModuleHealth("ok", "poller off")


def test_health_follows_a_running_poller_and_says_off_after_the_app_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, market_poller_enabled=True)
    started = threading.Event()

    def fake_run_poller(stop: threading.Event, provider: object) -> None:
        started.set()
        stop.wait()

    monkeypatch.setattr(poller, "run_poller", fake_run_poller)
    # Left over from before the app started. Starting the app clears it.
    poller._status.last_poll_failed = True

    with TestClient(create_app([PLUGIN])):
        assert started.wait(5)
        assert poller.health() == ModuleHealth("ok")

    assert poller.health() == ModuleHealth("ok", "poller off")


def test_health_says_stopped_when_the_thread_ends_while_the_app_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_settings(monkeypatch, market_poller_enabled=True)
    monkeypatch.setattr(poller, "run_poller", lambda stop, provider: None)

    with TestClient(create_app([PLUGIN])):
        assert wait_for(
            lambda: (
                poller.health() == ModuleHealth("degraded", "poller stopped")
            )
        )


def test_health_shows_a_failed_poll_while_the_poller_runs(
    monkeypatch: pytest.MonkeyPatch, test_sessions
) -> None:
    use_settings(monkeypatch, market_poller_enabled=True)
    real_run_poller = poller.run_poller
    polled = threading.Event()

    def failing_then_waiting(stop: threading.Event, provider: object) -> None:
        # One real poll that misses every price, then wait to be stopped.
        real_run_poller(
            stopped(),
            CountingProvider(MarketDataError("down")),
            lambda: OPEN,
            test_sessions,
        )
        polled.set()
        stop.wait()

    monkeypatch.setattr(poller, "run_poller", failing_then_waiting)

    with TestClient(create_app([PLUGIN])):
        assert polled.wait(5)
        assert poller.health() == ModuleHealth("degraded", "last poll failed")
