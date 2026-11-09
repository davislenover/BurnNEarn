"""Tests for the Money type that sends amounts to the phone."""

from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.core.money import Money


class Example(BaseModel):
    amount: Money


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (Decimal("84"), "84.0000"),
        (Decimal("-0"), "0.0000"),
        (Decimal("-12.3456"), "-12.3456"),
        (Decimal("1E+3"), "1000.0000"),
    ],
)
def test_money_is_sent_as_text_with_4_decimals(
    amount: Decimal, text: str
) -> None:
    assert Example(amount=amount).model_dump(mode="json") == {"amount": text}


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
