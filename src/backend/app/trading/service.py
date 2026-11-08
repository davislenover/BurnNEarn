"""Trading's rules: buying shares. Never commits."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import Money


class TradeRequest(BaseModel):
    """The body of POST /v1/me/trades.

    The phone never names a user. A field that isn't listed here, such as
    user_id, is refused, and the user comes from get_current_user.
    """

    model_config = ConfigDict(extra="forbid")

    # New for each buy the user confirms, and the same for each retry of it,
    # so a retry never buys twice.
    request_id: uuid.UUID
    symbol: str
    # Only buying for now, so anything else is refused.
    trade_type: Literal["buy"]
    # Whole shares, so 1.5 is refused. strict also refuses 1.0, "1" and true
    # instead of turning them into 1.
    quantity: int = Field(gt=0, strict=True)
    # The price the user saw, sent back exactly as GET /v1/assets gave it.
    # More than 4 decimals is refused.
    expected_price: Money
