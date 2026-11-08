"""Tests for how a DomainError, or a request that doesn't fit its route,
reaches the phone."""

from collections.abc import Iterator
from typing import Literal

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import DomainError
from app.core.money import Money
from app.core.plugins import Plugin
from app.main import app, create_app


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


class Order(BaseModel):
    quantity: int
    price: Money
    side: Literal["buy"]


def order_client() -> TestClient:
    """A small app with one route that takes an Order."""
    router = APIRouter()

    @router.post("/orders")
    def place(order: Order) -> dict[str, int]:
        return {"quantity": order.quantity}

    return TestClient(create_app([Plugin(name="probe", router=router)]))


GOOD = '"quantity": 1, "price": "101.5", "side": "buy"'


@pytest.mark.parametrize(
    "body",
    [
        # An ordinary bad value.
        '{"quantity": "one", "price": "101.5", "side": "buy"}',
        # Python reads these as numbers that JSON can't write back, and a
        # lone surrogate as text that can't be sent as UTF-8.
        '{"quantity": NaN, "price": "101.5", "side": "buy"}',
        '{"quantity": 1, "price": Infinity, "side": "buy"}',
        '{"quantity": 1e400, "price": "101.5", "side": "buy"}',
        '{"quantity": 1, "price": "101.5", "side": "\\ud800"}',
    ],
)
def test_a_body_that_doesnt_fit_is_a_422_without_the_values_sent(
    body: str,
) -> None:
    response = order_client().post(
        "/v1/orders",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors
    assert all("input" not in error for error in errors)


def test_a_422_keeps_fastapis_shape_without_the_values_sent() -> None:
    response = order_client().post(
        "/v1/orders",
        content='{"quantity": "one", "price": "101.50001", "side": "buy"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.json() == {
        "detail": [
            {
                "type": "int_parsing",
                "loc": ["body", "quantity"],
                "msg": "Input should be a valid integer, unable to parse "
                "string as an integer",
            },
            {
                "type": "decimal_max_places",
                "loc": ["body", "price"],
                "msg": "Decimal input should have no more than 4 decimal "
                "places",
                "ctx": {"decimal_places": 4},
            },
        ]
    }


def test_a_body_that_fits_still_works() -> None:
    response = order_client().post(
        "/v1/orders",
        content=f"{{{GOOD}}}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
