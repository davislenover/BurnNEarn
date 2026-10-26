"""Shared fixtures for backend tests.

Tests run against a real PostgreSQL database given by DATABASE_URL (the
local one from compose.yaml, or the service container in CI).
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.db import engine
from app.main import app


@pytest.fixture(scope="session")
def database() -> None:
    """Fail with a clear message if PostgreSQL is not running."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as error:
        pytest.fail(
            "Cannot reach PostgreSQL at DATABASE_URL. Start it with "
            f"`docker compose up -d` in src/backend. ({error.orig})",
            pytrace=False,
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    """An HTTP client that calls the app directly, without a server."""
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
