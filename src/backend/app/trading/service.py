"""Trading's rules: buying shares. Never commits."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.money import Money
from app.market.queries import (
    get_asset,
    get_asset_by_symbol,
    get_current_price,
    is_market_open,
)
from app.trading.models import Holding, Trade
from app.trading.types import (
    MarketClosedError,
    PriceChangedError,
    PriceOutOfDateError,
    RequestIdReusedError,
)
from app.wallet.interface import change_balance
from app.wallet.types import BalanceChangeReason, LockedPortfolio


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


def buy(
    session: Session,
    locked: LockedPortfolio,
    request: TradeRequest,
    now: datetime,
) -> tuple[Trade, bool]:
    """Buy whole shares for the locked portfolio. Returns the trade, and
    whether it is new.

    It pays with change_balance, adds the shares and records the trade, and
    never commits. The route commits once after it, so all three are saved
    together or not at all (FR_MktAtomicTrade).

    A request_id this portfolio already used is checked first. If it is the
    same trade, it is returned with new False and nothing changes, even
    after the market closes or the price moves. If it isn't, it raises
    RequestIdReusedError.

    A new request is refused, changing nothing, with the first of these that
    holds:
    - MarketClosedError: the market is closed
    - UnknownAssetError (404): no stock has the symbol
    - PriceOutOfDateError: the stock has no price yet, or it is delayed
    - PriceChangedError: the price isn't the one the user saw (SEC-29)
    - InsufficientFundsError: the balance is less than the cost
    """
    old = session.scalar(
        select(Trade).where(
            Trade.portfolio_id == locked.portfolio_id,
            Trade.request_id == request.request_id,
        )
    )
    if old is not None:
        if not _same_trade(session, old, request):
            raise RequestIdReusedError()
        return old, False

    if not is_market_open(now):
        raise MarketClosedError()
    asset = get_asset_by_symbol(session, request.symbol)
    current = get_current_price(session, asset.asset_id, now)
    if current is None or current.delayed:
        raise PriceOutOfDateError()
    if current.price != request.expected_price:
        raise PriceChangedError(current.price)

    # One price read is used for the check, the cost and the trade's price,
    # so the user pays exactly what they saw. The cost is a whole number
    # times the price, so it is exact.
    cost = request.quantity * current.price
    paid = change_balance(
        session, locked, -cost, BalanceChangeReason.TRADE_PURCHASE
    )
    _add_shares(session, locked.portfolio_id, asset.asset_id, request.quantity)
    trade = Trade(
        request_id=request.request_id,
        portfolio_id=locked.portfolio_id,
        asset_id=asset.asset_id,
        trade_type="buy",
        quantity=request.quantity,
        unit_price=current.price,
        currency_amount=cost,
        cash_balance_after=paid.cash_balance_after,
        status="executed",
        balance_change_id=paid.balance_change_id,
        created_at=now,
    )
    session.add(trade)
    session.flush()
    return trade, True


def _same_trade(session: Session, old: Trade, request: TradeRequest) -> bool:
    """Whether request asks for the trade old already made: the same stock,
    quantity and price."""
    return (
        get_asset(session, old.asset_id).symbol == request.symbol
        and old.quantity == request.quantity
        and old.unit_price == request.expected_price
    )


def _add_shares(
    session: Session,
    portfolio_id: uuid.UUID,
    asset_id: uuid.UUID,
    quantity: int,
) -> None:
    """Add shares to the portfolio's holding of one stock, making the
    holding if there is none.

    It is one statement, never a read then a write, so it stays right even
    if two buys ran at once.
    """
    new = insert(Holding).values(
        portfolio_id=portfolio_id, asset_id=asset_id, quantity=quantity
    )
    session.execute(
        new.on_conflict_do_update(
            index_elements=[Holding.portfolio_id, Holding.asset_id],
            set_={"quantity": Holding.quantity + new.excluded.quantity},
        )
    )
