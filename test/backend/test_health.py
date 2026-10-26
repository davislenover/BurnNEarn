"""Tests for GET /v1/health."""

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.db import get_db
from app.main import app


def test_health_is_ok_when_database_is_reachable(
    client: TestClient, database: None
) -> None:
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


class _UnreachableDatabase:
    """Stands in for a session whose database cannot be reached."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_reports_unavailable_database(client: TestClient) -> None:
    def unreachable_db() -> Iterator[_UnreachableDatabase]:
        yield _UnreachableDatabase()

    app.dependency_overrides[get_db] = unreachable_db

    response = client.get("/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
