"""Tests for buy: paying, adding the shares, recording the trade, refusing
a buy that breaks a rule, and applying each request_id once."""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import QUOTE_STALENESS_LIMIT
from app.market.models import Asset, Price
from app.market.types import UnknownAssetError
from app.trading.models import Holding, Trade
from app.trading.service import TradeRequest, buy
from app.trading.types import (
    MarketClosedError,
    PriceChangedError,
    PriceOutOfDateError,
    RequestIdReusedError,
)
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
# Just past the age at which an open market's price is delayed.
DELAYED = NOW - QUOTE_STALENESS_LIMIT - timedelta(microseconds=1)
# The same day at 16:30 in New York, after the close.
CLOSED = datetime(2026, 11, 9, 21, 30, tzinfo=UTC)


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
    symbol: str = "AAPL",
    quantity: int = 1,
    expected_price: str = "101.5",
    request_id: uuid.UUID | None = None,
) -> TradeRequest:
    """A buy request, with a new request_id unless one is given."""
    return TradeRequest(
        request_id=request_id or uuid.uuid4(),
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


@pytest.mark.parametrize(
    ("case", "error"),
    [
        # One rule broken.
        pytest.param({"now": CLOSED}, MarketClosedError, id="closed"),
        pytest.param({"symbol": "ZZZZ"}, UnknownAssetError, id="unknown"),
        pytest.param({"symbol": "MSFT"}, PriceOutOfDateError, id="no-price"),
        pytest.param(
            {"quoted_at": DELAYED}, PriceOutOfDateError, id="delayed"
        ),
        # The user saw 101.4999, then the price went up to 101.5.
        pytest.param(
            {"expected_price": "101.4999"}, PriceChangedError, id="went-up"
        ),
        pytest.param(
            {"expected_price": "101.5001"}, PriceChangedError, id="went-down"
        ),
        # Two rules broken. The first in the MIS order is the one refused.
        pytest.param(
            {"now": CLOSED, "symbol": "ZZZZ"},
            MarketClosedError,
            id="closed-and-unknown",
        ),
        pytest.param(
            {"now": CLOSED, "balance": "100"},
            MarketClosedError,
            id="closed-and-poor",
        ),
        pytest.param(
            {"quoted_at": DELAYED, "expected_price": "100"},
            PriceOutOfDateError,
            id="delayed-and-changed",
        ),
        pytest.param(
            {"expected_price": "100", "balance": "100"},
            PriceChangedError,
            id="changed-and-poor",
        ),
    ],
)
def test_a_buy_that_breaks_a_rule_is_refused_and_changes_nothing(
    session: Session, case: dict[str, Any], error: type[Exception]
) -> None:
    # A buy of 1 AAPL at 101.5 from 500, changed by case.
    case = {
        "now": NOW,
        "symbol": "AAPL",
        "quoted_at": A_MINUTE_AGO,
        "expected_price": "101.5",
        "balance": "500",
        **case,
    }
    locked = wallet(session, case["balance"])
    price(session, "AAPL", "101.5", case["quoted_at"])
    sent = request(case["symbol"], 1, case["expected_price"])

    with pytest.raises(error):
        buy(session, locked, sent, case["now"])

    assert get_balance(session, locked.portfolio_id) == Decimal(
        case["balance"]
    )
    assert count(session, Holding, locked) == 0
    assert count(session, Trade, locked) == 0
    assert count(session, BalanceChange, locked) == 1


def test_a_changed_price_is_refused_with_the_new_price(
    session: Session,
) -> None:
    # 3 shares at a price that needs all 4 decimals, so the error can't
    # pass by giving the cost or a rounded price instead.
    locked = wallet(session, "500")
    price(session, "AAPL", "33.3333")

    with pytest.raises(PriceChangedError) as refused:
        buy(session, locked, request("AAPL", 3, "33.3332"), NOW)

    assert refused.value.price == Decimal("33.3333")
    assert "33.3333" in refused.value.message


@pytest.mark.parametrize(
    ("quoted_at", "expected_price"),
    [
        # Exactly as old as allowed, so not delayed yet.
        (NOW - QUOTE_STALENESS_LIMIT, "101.5"),
        # The database gives back 101.5000, so the price is compared as a
        # number. The same number written another way is not a change.
        (A_MINUTE_AGO, "1.015E2"),
    ],
)
def test_a_buy_at_the_edge_of_a_rule_goes_through(
    session: Session, quoted_at: datetime, expected_price: str
) -> None:
    locked = wallet(session, "500")
    price(session, "AAPL", "101.5", quoted_at)

    trade, new = buy(
        session, locked, request(expected_price=expected_price), NOW
    )

    assert new
    assert trade.unit_price == Decimal("101.5")
    assert get_balance(session, locked.portfolio_id) == Decimal("398.5")


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


# Each request_id applies once (FR_MktNoDuplicate).


def test_the_same_request_twice_makes_one_trade(session: Session) -> None:
    # 2 shares, so the trade's cost (203) differs from its price (101.5).
    locked = wallet(session, "500")
    price(session, "AAPL", "101.5")
    sent = request("AAPL", 2)

    first, first_new = buy(session, locked, sent, NOW)
    again, again_new = buy(session, locked, sent, NOW)

    assert first_new
    assert not again_new
    assert again.trade_id == first.trade_id
    assert count(session, Trade, locked) == 1
    assert shares(session, locked) == 2
    # The funding and one payment.
    assert count(session, BalanceChange, locked) == 2
    assert get_balance(session, locked.portfolio_id) == Decimal("297")


@pytest.mark.parametrize(
    ("later", "new_price"),
    [
        pytest.param(CLOSED, None, id="after-the-close"),
        pytest.param(NOW + timedelta(minutes=2), "105", id="price-moved"),
        pytest.param(NOW + timedelta(minutes=20), None, id="price-delayed"),
    ],
)
def test_a_repeat_gets_its_first_trade_back_whatever_changed(
    session: Session, later: datetime, new_price: str | None
) -> None:
    # The first buy spends the whole balance, so a repeat that tried to pay
    # again would be refused too.
    locked = wallet(session, "101.5")
    price(session, "AAPL", "101.5")
    sent = request()
    first, _ = buy(session, locked, sent, NOW)
    if new_price is not None:
        price(session, "AAPL", new_price, later - timedelta(minutes=1))

    again, new = buy(session, locked, sent, later)

    assert not new
    assert again.trade_id == first.trade_id
    assert count(session, Trade, locked) == 1
    assert shares(session, locked) == 1
    assert get_balance(session, locked.portfolio_id) == Decimal("0")


def test_a_repeat_with_the_price_written_another_way_is_the_same_trade(
    session: Session,
) -> None:
    locked = wallet(session, "500")
    price(session, "AAPL", "101.5")
    sent = request()
    first, _ = buy(session, locked, sent, NOW)

    again, new = buy(
        session, locked, request("AAPL", 1, "1.015E2", sent.request_id), NOW
    )

    assert not new
    assert again.trade_id == first.trade_id


@pytest.mark.parametrize(
    "changed",
    [
        # The first trade was 2 AAPL at 101.5. Each case changes one thing,
        # up or down.
        pytest.param({"quantity": 3}, id="more"),
        pytest.param({"quantity": 1}, id="fewer"),
        pytest.param({"expected_price": "101.5001"}, id="higher-price"),
        pytest.param({"expected_price": "101.4999"}, id="lower-price"),
        pytest.param({"symbol": "MSFT"}, id="symbol"),
        pytest.param({"symbol": "aapl"}, id="symbol-case"),
        # The repeat is checked first, so these aren't unknown_asset or
        # market_closed.
        pytest.param({"symbol": "ZZZZ"}, id="unknown-symbol"),
        pytest.param({"quantity": 3, "now": CLOSED}, id="after-the-close"),
    ],
)
def test_the_same_request_id_for_a_different_trade_is_refused(
    session: Session, changed: dict[str, Any]
) -> None:
    locked = wallet(session, "500")
    price(session, "AAPL", "101.5")
    price(session, "MSFT", "400")
    sent = request("AAPL", 2)
    buy(session, locked, sent, NOW)
    case = {
        "now": NOW,
        "symbol": "AAPL",
        "quantity": 2,
        "expected_price": "101.5",
        **changed,
    }
    different = request(
        case["symbol"],
        case["quantity"],
        case["expected_price"],
        sent.request_id,
    )

    with pytest.raises(RequestIdReusedError):
        buy(session, locked, different, case["now"])

    assert count(session, Trade, locked) == 1
    assert shares(session, locked) == 2
    assert get_balance(session, locked.portfolio_id) == Decimal("297")


def test_another_users_same_request_id_makes_their_own_trade(
    session: Session,
) -> None:
    mine = wallet(session, "500")
    theirs = wallet(session, "500")
    price(session, "AAPL", "101.5")
    sent = request()
    my_trade, _ = buy(session, mine, sent, NOW)

    their_trade, new = buy(session, theirs, sent, NOW)

    assert new
    assert their_trade.trade_id != my_trade.trade_id
    assert their_trade.portfolio_id == theirs.portfolio_id
    # Their retry finds their own trade, not mine.
    again, again_new = buy(session, theirs, sent, NOW)
    assert not again_new
    assert again.trade_id == their_trade.trade_id
    assert shares(session, mine) == 1
    assert shares(session, theirs) == 1


def test_a_refused_request_saves_nothing_so_it_can_be_sent_again(
    session: Session,
) -> None:
    locked = wallet(session, "100")
    price(session, "AAPL", "101.5")
    sent = request()
    with pytest.raises(InsufficientFundsError):
        buy(session, locked, sent, NOW)
    change_balance(
        session,
        locked,
        Decimal("1.5"),
        BalanceChangeReason.ACTIVITY_REWARD,
        date(2026, 11, 9),
    )

    trade, new = buy(session, locked, sent, NOW)

    assert new
    assert trade.request_id == sent.request_id
    assert get_balance(session, locked.portfolio_id) == Decimal("0")
