"""Tests for GET /v1/health."""

from collections.abc import Iterator, Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.plugins import ModuleHealth, Plugin
from app.main import app, create_app


def test_health_is_ok_when_database_is_reachable(
    client: TestClient, database: None
) -> None:
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        # The poller is off in tests.
        "modules": {"market": {"status": "ok", "detail": "poller off"}},
    }


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
    assert response.json() == {
        "status": "degraded",
        "database": "unavailable",
        "modules": {"market": {"status": "ok", "detail": "poller off"}},
    }


def health_of(
    plugins: Sequence[Plugin], session: object
) -> tuple[int, dict[str, object]]:
    """GET /v1/health of an app built from plugins, using session."""
    small_app = create_app(plugins)

    def use_session() -> Iterator[object]:
        yield session

    small_app.dependency_overrides[get_db] = use_session
    response = TestClient(small_app).get("/v1/health")
    return response.status_code, response.json()


def test_each_module_with_a_health_check_is_reported(
    db_session: Session,
) -> None:
    plugins = [
        Plugin(name="quiet"),
        Plugin(name="busy", health=lambda: ModuleHealth("ok")),
    ]

    code, body = health_of(plugins, db_session)

    assert code == 200
    # A module without a health check is left out.
    assert body["modules"] == {"busy": {"status": "ok", "detail": None}}


def test_a_degraded_module_makes_health_degraded_but_still_answers_200(
    db_session: Session,
) -> None:
    plugins = [
        Plugin(name="fine", health=lambda: ModuleHealth("ok")),
        Plugin(
            name="behind",
            health=lambda: ModuleHealth("degraded", "poller stopped"),
        ),
    ]

    code, body = health_of(plugins, db_session)

    assert code == 200
    assert body == {
        "status": "degraded",
        "database": "ok",
        "modules": {
            "fine": {"status": "ok", "detail": None},
            "behind": {"status": "degraded", "detail": "poller stopped"},
        },
    }


def test_a_failing_health_check_is_reported_without_its_error(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    def broken() -> ModuleHealth:
        raise RuntimeError("secret detail")

    code, body = health_of([Plugin(name="broken", health=broken)], db_session)

    assert code == 200
    assert body["status"] == "degraded"
    assert body["modules"] == {
        "broken": {"status": "degraded", "detail": "health check failed"}
    }
    assert "secret detail" not in str(body)
    # The team still finds out why, from the log.
    assert "secret detail" in caplog.text


def test_an_unreachable_database_answers_503_even_if_modules_are_ok() -> None:
    plugins = [Plugin(name="fine", health=lambda: ModuleHealth("ok"))]

    code, body = health_of(plugins, _UnreachableDatabase())

    assert code == 503
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    # The modules are still reported.
    assert body["modules"] == {"fine": {"status": "ok", "detail": None}}


@pytest.mark.parametrize(
    "result",
    # Nothing, a plain string, and a status that is not ok or degraded.
    [None, "ok", ModuleHealth("fine")],
)
def test_a_health_check_that_returns_the_wrong_thing_counts_as_failed(
    db_session: Session, result: object
) -> None:
    plugins = [Plugin(name="odd", health=lambda: result)]

    code, body = health_of(plugins, db_session)

    assert code == 200
    assert body["modules"] == {
        "odd": {"status": "degraded", "detail": "health check failed"}
    }
