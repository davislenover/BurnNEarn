"""Tests for the trade request and trading's refusals."""

import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.errors import DomainError
from app.trading.service import TradeRequest
from app.trading.types import (
    MarketClosedError,
    PriceChangedError,
    PriceOutOfDateError,
    RequestIdReusedError,
)

# A body as the phone sends it, after the JSON is read.
GOOD = {
    "request_id": "6f1c2b7e-1f4a-4c55-9d0e-3b8f2a1c9d10",
    "symbol": "AAPL",
    "trade_type": "buy",
    "quantity": 1,
    "expected_price": "101.5",
}


def test_a_good_request_is_accepted() -> None:
    request = TradeRequest.model_validate(GOOD)

    assert request.request_id == uuid.UUID(GOOD["request_id"])
    assert request.symbol == "AAPL"
    assert request.trade_type == "buy"
    assert request.quantity == 1
    # Kept exact, never turned into a float.
    assert request.expected_price == Decimal("101.5")
    assert isinstance(request.expected_price, Decimal)


@pytest.mark.parametrize("make_id", [uuid.uuid1, uuid.uuid4, uuid.uuid7])
def test_a_request_id_of_any_uuid_version_is_accepted(
    make_id: Callable[[], uuid.UUID],
) -> None:
    request_id = make_id()

    request = TradeRequest.model_validate(
        {**GOOD, "request_id": str(request_id)}
    )

    assert request.request_id == request_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # Only buying for now.
        ("trade_type", "sell"),
        # Whole shares, at least 1, never converted from another type.
        ("quantity", 0),
        ("quantity", -1),
        ("quantity", 1.5),
        ("quantity", 1.0),
        ("quantity", "1"),
        ("quantity", True),
        # Amounts have at most 4 decimals, and must be numbers.
        ("expected_price", "101.50001"),
        ("expected_price", "NaN"),
        ("expected_price", "Infinity"),
        ("request_id", "not-a-uuid"),
        ("symbol", 123),
    ],
)
def test_a_bad_field_is_refused(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        TradeRequest.model_validate({**GOOD, field: value})


@pytest.mark.parametrize("field", list(GOOD))
def test_a_missing_field_is_refused(field: str) -> None:
    body = {name: value for name, value in GOOD.items() if name != field}

    with pytest.raises(ValidationError):
        TradeRequest.model_validate(body)


def test_the_phone_cannot_name_a_user() -> None:
    with pytest.raises(ValidationError):
        TradeRequest.model_validate({**GOOD, "user_id": str(uuid.uuid4())})


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (RequestIdReusedError(), "request_id_reused"),
        (MarketClosedError(), "market_closed"),
        (PriceOutOfDateError(), "price_out_of_date"),
        (PriceChangedError(Decimal("101.5")), "price_changed"),
    ],
)
def test_each_refusal_has_its_code_and_status_409(
    error: DomainError, code: str
) -> None:
    assert isinstance(error, DomainError)
    assert error.code == code
    assert error.status == 409
    # Each has its own message, not DomainError's.
    assert error.message != DomainError.message


def test_price_changed_gives_the_new_price_with_4_decimals() -> None:
    error = PriceChangedError(Decimal("101.5"))

    assert error.price == Decimal("101.5")
    assert error.message == (
        "The price is now 101.5000. Check it and confirm again."
    )


def test_price_changed_cannot_be_raised_without_the_price() -> None:
    with pytest.raises(TypeError):
        PriceChangedError()  # type: ignore[call-arg]
