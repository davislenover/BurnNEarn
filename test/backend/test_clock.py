"""Tests for the clock that routes and services take the time from."""

from datetime import UTC, datetime, timedelta

from app.core.clock import get_clock, system_clock


def test_the_system_clock_gives_the_current_time_in_utc() -> None:
    now = system_clock()

    assert now.tzinfo is UTC
    assert abs(datetime.now(UTC) - now) < timedelta(seconds=5)
    # Routes get the clock itself, not one reading of it.
    assert get_clock() is system_clock
