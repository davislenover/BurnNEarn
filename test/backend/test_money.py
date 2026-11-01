"""Tests for the Money type that sends amounts to the phone."""

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.api.common import Money


class Example(BaseModel):
    amount: Money


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (Decimal("84"), "84.0000"),
        (84, "84.0000"),
        (Decimal("84.5"), "84.5000"),
        (Decimal("0"), "0.0000"),
        (Decimal("-0"), "0.0000"),
        (Decimal("-12.3456"), "-12.3456"),
        (Decimal("1E+3"), "1000.0000"),
    ],
)
def test_money_is_sent_as_text_with_4_decimals(
    amount: Decimal | int, text: str
) -> None:
    assert Example(amount=amount).model_dump(mode="json") == {"amount": text}


def test_a_route_sends_money_as_text() -> None:
    probe = FastAPI()

    @probe.get("/example")
    def example() -> Example:
        return Example(amount=Decimal("84"))

    assert TestClient(probe).get("/example").json() == {"amount": "84.0000"}


def test_money_stays_a_decimal_in_python() -> None:
    example = Example(amount="412.0000")

    assert example.amount == Decimal("412")
    assert example.model_dump() == {"amount": Decimal("412")}


def test_money_with_more_than_4_decimals_is_refused() -> None:
    with pytest.raises(ValidationError):
        Example(amount=Decimal("1.23456"))


def test_response_docs_say_money_is_text() -> None:
    schema = Example.model_json_schema(mode="serialization")

    assert schema["properties"]["amount"]["type"] == "string"
