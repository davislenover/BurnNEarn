"""Tests for how a DomainError reaches the phone."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.errors import DomainError
from app.main import app


class OutOfStockError(DomainError):
    code = "out_of_stock"
    message = "That is out of stock."
    status = 409


@pytest.fixture
def real_client() -> Iterator[TestClient]:
    """A client for the real app, with a route that raises OutOfStockError."""

    def raise_out_of_stock(message: str | None = None) -> None:
        raise OutOfStockError(message)

    app.add_api_route("/raises-out-of-stock", raise_out_of_stock)
    yield TestClient(app)
    app.router.routes.pop()


def test_domain_error_becomes_json_with_its_status(
    real_client: TestClient,
) -> None:
    response = real_client.get("/raises-out-of-stock")

    assert response.status_code == 409
    assert response.json() == {
        "detail": {"code": "out_of_stock", "message": "That is out of stock."}
    }


def test_a_message_can_be_set_when_the_error_is_raised(
    real_client: TestClient,
) -> None:
    response = real_client.get(
        "/raises-out-of-stock", params={"message": "Only 2 left."}
    )

    assert response.json()["detail"] == {
        "code": "out_of_stock",
        "message": "Only 2 left.",
    }


def test_setting_a_message_does_not_change_the_class() -> None:
    OutOfStockError("Only 2 left.")

    assert OutOfStockError().message == "That is out of stock."
