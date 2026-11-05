"""Shared fixtures for backend tests.

Tests only ever run on a database whose name ends in _test, so they can't
touch data you use for anything else. If DATABASE_URL names "fitfolio", tests
use "fitfolio_test" on the same server. CI already names "fitfolio_test".

Each run rebuilds that database and ends any other run using it. To run two at
once, such as from two git worktrees, give each its own DATABASE_URL ending in
_test.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.settings import Settings

ALEMBIC_INI = Path(__file__).parents[2] / "src" / "backend" / "alembic.ini"

# The app connects using DATABASE_URL as soon as app.core.db is imported, so
# this has to be set before that import.
_url = make_url(Settings().database_url)
if not _url.database.endswith("_test"):
    _url = _url.set(database=f"{_url.database}_test")
TEST_DATABASE_URL = _url
os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(
    hide_password=False
)
# Every test gets made-up prices, the exchange's real hours and no poller,
# whatever your own .env says. Environment variables win over .env.
os.environ["MARKET_PROVIDER"] = "fake"
os.environ["MARKET_ALWAYS_OPEN"] = "false"
# A running poller would save real rows that the tests never undo.
os.environ["MARKET_POLLER_ENABLED"] = "false"

from app.core.db import SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402

# Stops the run if something imported the app before this file. The tests would
# otherwise run on whatever database DATABASE_URL names.
assert engine.url.database == TEST_DATABASE_URL.database
assert engine.url.database.endswith("_test")


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    """The settings Alembic needs to find the migrations."""
    return Config(ALEMBIC_INI)


@pytest.fixture(scope="session")
def database(alembic_config: Config) -> None:
    """Rebuild the test database from the migrations, once per test run.

    It is dropped rather than downgraded, because a database left at another
    branch's migration can't be downgraded from this branch.
    """
    # You can't drop a database while connected to it, so connect to the
    # "postgres" database that every PostgreSQL server has.
    admin = create_engine(
        TEST_DATABASE_URL.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    name = admin.dialect.identifier_preparer.quote(TEST_DATABASE_URL.database)
    try:
        with admin.connect() as connection:
            connection.execute(
                text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
            )
            connection.execute(text(f"CREATE DATABASE {name}"))
    except OperationalError as error:
        pytest.fail(
            "Cannot reach PostgreSQL at DATABASE_URL. Start it with "
            f"`docker compose up -d` in src/backend. ({error.orig})",
            pytrace=False,
        )
    finally:
        admin.dispose()
    command.upgrade(alembic_config, "head")


@pytest.fixture
def db_session(database: None) -> Iterator[Session]:
    """A session whose changes are all undone when the test ends.

    The whole test runs inside one transaction that is never saved. A commit
    in the code under test only saves up to a checkpoint inside it (a
    savepoint), so the code behaves normally and the rollback still undoes it.

    Two things to watch for:
    - Code under test must use this session, not SessionLocal or engine.
      Otherwise its rows are really saved, and it can wait forever on rows
      this session holds.
    - now() stays the same for the whole test and ids are not reset, so don't
      check order by now() columns or exact id values.
    """
    with engine.connect() as connection:
        transaction = connection.begin()
        session = SessionLocal(
            bind=connection, join_transaction_mode="create_savepoint"
        )
        yield session
        session.close()
        transaction.rollback()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """An HTTP client that calls the app directly, without a server.

    Routes use db_session. Like the real get_db, each request ends by dropping
    whatever the route did not commit, so a forgotten commit fails the test.
    Commit any rows you set up, or routes won't see them. Send requests one at
    a time, since they share one session.
    """

    def use_test_session() -> Iterator[Session]:
        try:
            yield db_session
        finally:
            db_session.rollback()

    app.dependency_overrides[get_db] = use_test_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
