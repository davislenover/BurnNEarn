"""Tests for the shared test setup in conftest.py."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import engine, get_db
from app.main import app
from app.market.models import Asset


def test_tests_run_on_a_database_ending_in_test(db_session: Session) -> None:
    name = db_session.execute(select(func.current_database())).scalar_one()

    assert name.endswith("_test")


def test_a_commit_in_a_test_never_reaches_the_database(
    db_session: Session,
) -> None:
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


@pytest.mark.parametrize("run", [1, 2])
def test_a_commit_is_undone_when_the_test_ends(
    db_session: Session, run: int
) -> None:
    # The second run would break the unique symbol rule if the first one's
    # row were still there.
    db_session.add(Asset(symbol="TWICE", name="Twice", asset_type="stock"))
    db_session.commit()


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

    assert response.json() == {"status": "ok", "database": "ok"}
