"""Trading's HTTP routes: buying shares, and the portfolio's value."""

import uuid
from datetime import UTC, datetime
from typing import Literal, Self

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.clock import Clock, get_clock
from app.core.db import get_db
from app.core.money import Money
from app.trading.models import Trade
from app.trading.service import (
    PortfolioValue,
    TradeRequest,
    buy,
    portfolio_value,
)
from app.users.interface import get_current_user
from app.users.types import CurrentUser
from app.wallet.interface import lock_live_portfolio
from app.wallet.queries import live_portfolio_id

router = APIRouter(tags=["trading"])


class TradeReceipt(BaseModel):
    """What POST /v1/me/trades sends back. A repeat of a request gets the
    same body as the first answer."""

    trade_id: uuid.UUID
    status: str
    # The price paid for each share.
    unit_price: Money
    # What the trade cost.
    currency_amount: Money
    executed_at: datetime
    # The balance right after this trade.
    cash_balance: Money

    @classmethod
    def of(cls, trade: Trade) -> Self:
        return cls(
            trade_id=trade.trade_id,
            status=trade.status,
            unit_price=trade.unit_price,
            currency_amount=trade.currency_amount,
            # PostgreSQL gives a stored time back in the session's time zone,
            # so it is sent in UTC to keep a repeat's body the same.
            executed_at=trade.created_at.astimezone(UTC),
            cash_balance=trade.cash_balance_after,
        )


@router.post("/me/trades", status_code=status.HTTP_201_CREATED)
def post_trade(
    request: TradeRequest,
    response: Response,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
    user: CurrentUser = Depends(get_current_user),
) -> TradeReceipt:
    """Buy whole shares for the current user (FR_MktBuy).

    A new trade is 201. A repeat of a request_id is 200 with the same body,
    so a retry never buys twice (FR_MktNoDuplicate).
    """
    # Lock first, so requests for this portfolio take turns, and a repeat
    # that waited here finds the trade the first one made.
    locked = lock_live_portfolio(db, user.user_id)
    trade, new = buy(db, locked, request, clock())
    # Built before the commit, so nothing has to be reloaded after it.
    receipt = TradeReceipt.of(trade)
    # Once, so the payment, the shares and the trade are saved together.
    db.commit()
    if not new:
        response.status_code = status.HTTP_200_OK
    return receipt


class PortfolioReply(PortfolioValue):
    """What GET /v1/me/portfolio sends back."""

    # The JSON schema lists simulated as always sent, though it has a
    # default.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    # Always true, so the phone labels the values as simulated
    # (FR_MktLabelReturns).
    simulated: Literal[True] = True


@router.get("/me/portfolio")
def get_portfolio(
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
    user: CurrentUser = Depends(get_current_user),
) -> PortfolioReply:
    """The current user's live portfolio at the latest prices
    (FR_MktHoldings, FR_MktPortfolioValue).

    It only reads, so it doesn't lock or commit.
    """
    value = portfolio_value(db, live_portfolio_id(db, user.user_id), clock())
    return PortfolioReply(**dict(value))
