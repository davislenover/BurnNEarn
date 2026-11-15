"""Concurrent HTTP syncs wait on the wallet lock and pay a day once."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event, Lock
from time import monotonic
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.activity import routes
from app.activity.models import ActivityDailyTotal
from app.core.clock import get_clock
from app.core.db import SessionLocal, engine
from app.main import app
from app.users.interface import create_user, get_current_user
from app.users.models import User
from app.users.types import CurrentUser
from app.wallet.interface import create_live_portfolio, delete_portfolio
from app.wallet.models import BalanceChange
from app.wallet.queries import get_balance


def test_concurrent_syncs_lock_before_reading_rewards(
    database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with SessionLocal() as session:
        user_id = create_user(session)
        portfolio_id = create_live_portfolio(session, user_id)
        session.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=user_id
    )
    app.dependency_overrides[get_clock] = lambda: (
        lambda: datetime(2026, 11, 12, 15, tzinfo=UTC)
    )
    entered = Event()
    release = Event()
    guard = Lock()
    calls = 0
    sync = routes.sync_daily_totals

    def hold_first(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        with guard:
            calls += 1
            first = calls == 1
        if first:
            entered.set()
            assert release.wait(5), "first sync was never released"
        return sync(*args, **kwargs)

    monkeypatch.setattr(routes, "sync_daily_totals", hold_first)
    sent = {
        "time_zone": "America/Toronto",
        "totals": [
            {
                "activity_date": "2026-11-12",
                "activity_type": "steps",
                "step_count": 8421,
            }
        ],
    }

    def put() -> dict[str, Any]:
        with TestClient(app) as client:
            response = client.put("/v1/me/activity/daily-totals", json=sent)
            assert response.status_code == 200
            return response.json()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(put)
            try:
                assert entered.wait(5), "first sync never acquired the lock"
                second = workers.submit(put)
                # Observe an actual PostgreSQL lock wait, not a guessed
                # thread scheduling delay. Only this test uses this DB now.
                deadline = monotonic() + 3
                waiting = False
                while monotonic() < deadline and not second.done():
                    with engine.connect() as connection:
                        waiting = connection.scalar(
                            text(
                                "SELECT EXISTS (SELECT 1 "
                                "FROM pg_stat_activity "
                                "WHERE datname = current_database() "
                                "AND wait_event_type = 'Lock' "
                                "AND query LIKE '%FOR UPDATE%')"
                            )
                        )
                    if waiting:
                        break
                    Event().wait(0.02)
                assert waiting, (
                    "second sync did not wait on the portfolio lock"
                )
                assert calls == 1
            finally:
                release.set()
            first_reply = first.result(timeout=5)
            second_reply = second.result(timeout=5)
            assert first_reply["totals"][0]["credited_now"] == "84.0000"
            assert second_reply["totals"][0]["credited_now"] == "0.0000"
            assert first_reply["cash_balance"] == "84.0000"
            assert second_reply["cash_balance"] == "84.0000"
        with SessionLocal() as session:
            assert get_balance(session, portfolio_id) == 84
            assert (
                session.scalar(
                    select(func.count()).where(
                        ActivityDailyTotal.user_id == user_id
                    )
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count()).where(
                        BalanceChange.portfolio_id == portfolio_id
                    )
                )
                == 1
            )
    finally:
        release.set()
        app.dependency_overrides.clear()
        with SessionLocal() as session:
            delete_portfolio(session, portfolio_id)
            owner = session.get(User, user_id)
            if owner is not None:
                session.delete(owner)
            session.commit()
