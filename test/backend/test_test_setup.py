"""Tests for the shared test setup in conftest.py."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import engine, get_db
from app.main import app
from app.market.models import Asset
from app.wallet.queries import activity_paid, get_balance, live_portfolio_id

# The fixture's type. It is defined in conftest.py, which tests don't
# import.
MakePortfolio = Callable[..., Any]


@pytest.mark.parametrize("run", [1, 2])
def test_a_commit_in_a_test_never_reaches_the_database(
    db_session: Session, run: int
) -> None:
    # The second run would break the unique symbol rule if the first one's
    # row were still there.
    db_session.add(Asset(symbol="TEMP", name="Temp", asset_type="stock"))
    db_session.commit()

    count_temp_rows = (
        select(func.count()).select_from(Asset).where(Asset.symbol == "TEMP")
    )

    assert db_session.execute(count_temp_rows).scalar_one() == 1
    # A separate connection only sees what was really saved.
    with engine.connect() as other_connection:
        assert other_connection.execute(count_temp_rows).scalar_one() == 0


def test_a_rollback_only_undoes_back_to_the_last_commit(
    db_session: Session,
) -> None:
    db_session.add(Asset(symbol="KEEP", name="Keep", asset_type="stock"))
    db_session.commit()

    db_session.add(Asset(symbol="AAPL", name="Repeat", asset_type="stock"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    kept = db_session.scalars(
        select(Asset.symbol).where(Asset.symbol == "KEEP")
    ).all()
    assert kept == ["KEEP"]


@pytest.mark.parametrize(("route_commits", "rows"), [(True, 1), (False, 0)])
def test_a_route_keeps_a_row_only_if_it_commits(
    client: TestClient, db_session: Session, route_commits: bool, rows: int
) -> None:
    probe = FastAPI()
    probe.dependency_overrides = app.dependency_overrides

    @probe.post("/add")
    def add(db: Session = Depends(get_db)) -> None:
        db.add(Asset(symbol="ROUTE", name="Route", asset_type="stock"))
        db.flush()
        if route_commits:
            db.commit()

    TestClient(probe).post("/add")

    count_route_rows = (
        select(func.count()).select_from(Asset).where(Asset.symbol == "ROUTE")
    )
    assert db_session.execute(count_route_rows).scalar_one() == rows


def test_the_real_get_db_works(database: None) -> None:
    with TestClient(app) as real_client:
        response = real_client.get("/v1/health")

    assert response.json() == {
        "status": "ok",
        "database": "ok",
        # The poller is off in tests.
        "modules": {"market": {"status": "ok", "detail": "poller off"}},
    }


def test_make_portfolio_funds_one_old_reward_and_commits(
    db_session: Session, make_portfolio: MakePortfolio
) -> None:
    owner = make_portfolio(Decimal("500"))
    # A rollback can't undo it, because it was committed.
    db_session.rollback()

    assert get_balance(db_session, owner.portfolio_id) == Decimal("500")
    assert activity_paid(
        db_session, owner.portfolio_id, date(2000, 1, 1)
    ) == Decimal("500")
    assert live_portfolio_id(db_session, owner.user.user_id) == (
        owner.portfolio_id
    )
