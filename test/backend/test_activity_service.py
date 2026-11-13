"""The service leaves its transaction open for its caller."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.activity.models import ActivityDailyTotal
from app.activity.schemas import DailyTotalsRequest
from app.activity.service import sync_daily_totals
from app.wallet.interface import lock_live_portfolio
from app.wallet.queries import get_balance


def test_the_service_never_commits_and_its_work_can_be_rolled_back(
    db_session: Session,
    make_portfolio: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_portfolio()

    def no_commit() -> None:
        raise AssertionError("sync_daily_totals must never commit")

    monkeypatch.setattr(db_session, "commit", no_commit)
    request = DailyTotalsRequest.model_validate(
        {
            "time_zone": "America/Toronto",
            "totals": [
                {
                    "activity_date": "2026-11-12",
                    "activity_type": "steps",
                    "step_count": 8421,
                }
            ],
        }
    )
    locked = lock_live_portfolio(db_session, owner.user.user_id)
    results = sync_daily_totals(
        db_session, locked, request, datetime(2026, 11, 12, 15, tzinfo=UTC)
    )
    assert len(results) == 1
    assert results[0].reward == 84
    assert results[0].credited_now == 84
    assert get_balance(db_session, owner.portfolio_id) == 84
    db_session.rollback()
    assert get_balance(db_session, owner.portfolio_id) == 0
    assert (
        db_session.get(
            ActivityDailyTotal,
            (owner.user.user_id, date(2026, 11, 12), "steps"),
        )
        is None
    )
