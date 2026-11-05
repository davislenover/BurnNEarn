"""Tests for the clock that routes and services take the time from."""

from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.clock import Clock, get_clock, system_clock


def test_the_system_clock_gives_the_current_time_in_utc() -> None:
    now = system_clock()

    assert now.tzinfo is UTC
    assert abs(datetime.now(UTC) - now) < timedelta(seconds=5)


def test_a_test_can_set_the_time_a_route_sees() -> None:
    fixed = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
    probe = FastAPI()

    @probe.get("/now")
    def now(clock: Clock = Depends(get_clock)) -> dict[str, str]:
        return {"now": clock().isoformat()}

    probe.dependency_overrides[get_clock] = lambda: lambda: fixed

    response = TestClient(probe).get("/now")

    assert response.json() == {"now": fixed.isoformat()}
