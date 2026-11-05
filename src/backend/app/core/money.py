"""Money: the type for amounts sent to the phone."""

from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer


def _to_text(amount: Decimal) -> str:
    # The z stops a zero from showing as "-0.0000".
    return f"{amount:z.4f}"


# Amounts go to the phone as text with 4 decimals, such as "84.0000", because
# JSON numbers can lose exactness on the way. When a model is built, an amount
# with more than 4 decimals is refused instead of being quietly rounded, so
# round one that comes from a division or avg() first, with
# .quantize(Decimal("0.0001")). Python code keeps getting a Decimal. Only JSON
# gets the text.
Money = Annotated[
    Decimal,
    Field(decimal_places=4),
    PlainSerializer(_to_text, return_type=str, when_used="json"),
]
