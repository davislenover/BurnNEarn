"""Tests for buy: paying, adding the shares and recording the trade."""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.market.models import Asset, Price
from app.trading.models import Holding, Trade
from app.trading.service import TradeRequest, buy
from app.trading.types import PriceOutOfDateError
from app.users.interface import create_user
from app.wallet.interface import (
    change_balance,
    create_live_portfolio,
    lock_live_portfolio,
)
from app.wallet.models import BalanceChange
from app.wallet.queries import get_balance
from app.wallet.types import (
    BalanceChangeReason,
    InsufficientFundsError,
    LockedPortfolio,
)

# The fixtures' types. They are defined in conftest.py, which tests don't
# import.
AddPrice = Callable[[str, str, datetime], None]
MakePortfolio = Callable[..., Any]

# Monday, Nov 9, 2026 at 10:00 in New York, while the market is open.
NOW = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)
A_MINUTE_AGO = NOW - timedelta(minutes=1)


@pytest.fixture
def session(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """db_session, but a commit fails the test. buy never commits: the route
    commits once after it, so a buy is all or nothing."""

    def no_commit() -> None:
        raise AssertionError("buy must never commit")

    monkeypatch.setattr(db_session, "commit", no_commit)
    return db_session


def wallet(session: Session, balance: str) -> LockedPortfolio:
    """A new user's live portfolio with this balance, locked."""
    user_id = create_user(session)
    create_live_portfolio(session, user_id)
    locked = lock_live_portfolio(session, user_id)
    change_balance(
        session,
        locked,
        Decimal(balance),
        BalanceChangeReason.ACTIVITY_REWARD,
        date(2026, 11, 8),
    )
    return locked


def asset_id(session: Session, symbol: str) -> uuid.UUID:
    return session.execute(
        select(Asset.asset_id).where(Asset.symbol == symbol)
    ).scalar_one()


def price(
    session: Session,
    symbol: str,
    value: str,
    quoted_at: datetime = A_MINUTE_AGO,
) -> None:
    session.add(
        Price(
            asset_id=asset_id(session, symbol),
            price=Decimal(value),
            quoted_at=quoted_at,
        )
    )
    session.flush()


def request(
    symbol: str = "AAPL", quantity: int = 1, expected_price: str = "101.5"
) -> TradeRequest:
    return TradeRequest(
        request_id=uuid.uuid4(),
        symbol=symbol,
        trade_type="buy",
        quantity=quantity,
        expected_price=Decimal(expected_price),
    )


def shares(
    session: Session, locked: LockedPortfolio, symbol: str = "AAPL"
) -> int | None:
    """The portfolio's shares of one stock, or None with no holding row.

    Read with a select, since the upsert doesn't refresh rows already
    loaded."""
    return session.scalar(
        select(Holding.quantity).where(
            Holding.portfolio_id == locked.portfolio_id,
            Holding.asset_id == asset_id(session, symbol),
        )
    )


def count(session: Session, table: type, locked: LockedPortfolio) -> int:
    return session.execute(
        select(func.count()).where(table.portfolio_id == locked.portfolio_id)
    ).scalar_one()


@pytest.mark.parametrize(
    ("balance", "quantity", "unit_price", "cost", "left"),
    [
        ("500", 1, "101.5", "101.5", "398.5"),
        # Exact to the last of 4 decimals.
        ("100", 3, "33.3333", "99.9999", "0.0001"),
        # The whole balance can be spent.
        ("101.5", 1, "101.5", "101.5", "0"),
    ],
)
def test_a_buy_pays_exactly_and_adds_the_shares(
    session: Session,
    balance: str,
    quantity: int,
    unit_price: str,
    cost: str,
    left: str,
) -> None:
    locked = wallet(session, balance)
    price(session, "AAPL", unit_price)

    trade, new = buy(
        session, locked, request("AAPL", quantity, unit_price), NOW
    )

    assert new
    assert get_balance(session, locked.portfolio_id) == Decimal(left)
    assert shares(session, locked) == quantity
    session.refresh(trade)
    assert trade.quantity == quantity
    assert trade.unit_price == Decimal(unit_price)
    assert trade.currency_amount == Decimal(cost)
    assert trade.cash_balance_after == Decimal(left)


def test_the_trade_records_the_request_and_its_own_payment(
    session: Session,
) -> None:
    locked = wallet(session, "500")
    price(session, "AAPL", "101.5")
    sent = request()

    trade, _ = buy(session, locked, sent, NOW)

    session.refresh(trade)
    assert trade.request_id == sent.request_id
    assert trade.portfolio_id == locked.portfolio_id
    assert trade.asset_id == asset_id(session, "AAPL")
    assert trade.trade_type == "buy"
    assert trade.status == "executed"
    assert trade.created_at == NOW
    # Paid from this portfolio, by one purchase of exactly the cost.
    payment = session.get(BalanceChange, trade.balance_change_id)
    assert payment is not None
    assert payment.portfolio_id == locked.portfolio_id
    assert payment.amount == Decimal("-101.5")
    assert payment.reason == BalanceChangeReason.TRADE_PURCHASE


def test_a_buy_uses_the_newest_price(session: Session) -> None:
    locked = wallet(session, "500")
    price(session, "AAPL", "100", quoted_at=NOW - timedelta(minutes=2))
    price(session, "AAPL", "101.5")

    trade, _ = buy(session, locked, request(), NOW)

    assert trade.unit_price == Decimal("101.5")
    assert get_balance(session, locked.portfolio_id) == Decimal("398.5")


def test_more_buys_add_to_one_holding_per_stock(session: Session) -> None:
    locked = wallet(session, "1000")
    price(session, "AAPL", "101.5")
    price(session, "MSFT", "400")

    buy(session, locked, request("AAPL", 1), NOW)
    buy(session, locked, request("AAPL", 2), NOW)
    buy(session, locked, request("MSFT", 1, "400"), NOW)

    assert shares(session, locked, "AAPL") == 3
    assert shares(session, locked, "MSFT") == 1
    assert count(session, Holding, locked) == 2
    assert count(session, Trade, locked) == 3
    assert get_balance(session, locked.portfolio_id) == Decimal("295.5")


@pytest.mark.parametrize(
    "quantity",
    [
        1,
        # More than an Integer column holds. The balance is checked before
        # any share is written, so this is refused for its cost instead.
        2**31,
    ],
)
def test_not_enough_currency_is_refused_and_changes_nothing(
    session: Session, quantity: int
) -> None:
    locked = wallet(session, "100")
    price(session, "AAPL", "101.5")

    with pytest.raises(InsufficientFundsError):
        buy(session, locked, request(quantity=quantity), NOW)

    assert get_balance(session, locked.portfolio_id) == Decimal("100")
    assert shares(session, locked) is None
    assert count(session, Trade, locked) == 0
    # Only the change that funded the wallet.
    assert count(session, BalanceChange, locked) == 1


def test_a_stock_with_no_price_yet_is_refused_and_changes_nothing(
    session: Session,
) -> None:
    locked = wallet(session, "500")

    with pytest.raises(PriceOutOfDateError):
        buy(session, locked, request(), NOW)

    assert get_balance(session, locked.portfolio_id) == Decimal("500")
    assert shares(session, locked) is None
    assert count(session, Trade, locked) == 0


def test_a_buy_that_is_rolled_back_leaves_nothing(
    db_session: Session,
    make_portfolio: MakePortfolio,
    add_price: AddPrice,
) -> None:
    # FR_MktAtomicTrade: the payment, the shares and the trade are saved
    # together or not at all. The setup is committed, the buy is not.
    owner = make_portfolio(Decimal("500"))
    add_price("AAPL", "101.5", A_MINUTE_AGO)
    locked = lock_live_portfolio(db_session, owner.user.user_id)
    buy(db_session, locked, request(), NOW)

    db_session.rollback()

    assert get_balance(db_session, locked.portfolio_id) == Decimal("500")
    assert shares(db_session, locked) is None
    assert count(db_session, Trade, locked) == 0
    assert count(db_session, BalanceChange, locked) == 1
