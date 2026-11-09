"""Tests for the trades and holdings tables (trading_0001).

These check the rules the database itself keeps, so they hold even for
code that skips trading's own functions.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Connection, delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import engine
from app.market.models import Asset
from app.trading.models import Holding, Trade
from app.users.models import User
from app.wallet.interface import delete_portfolio
from app.wallet.models import BalanceChange, Portfolio

AT = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)


@pytest.fixture
def connection(database: None) -> Iterator[Connection]:
    """A connection whose changes are all undone when the test ends."""
    with engine.connect() as connection:
        yield connection
        connection.rollback()


def new_portfolio(connection: Connection) -> uuid.UUID:
    user_id = connection.execute(
        insert(User)
        .values(time_zone="America/Toronto")
        .returning(User.user_id)
    ).scalar_one()
    return connection.execute(
        insert(Portfolio)
        .values(user_id=user_id)
        .returning(Portfolio.portfolio_id)
    ).scalar_one()


def asset_id(connection: Connection, symbol: str = "AAPL") -> uuid.UUID:
    return connection.execute(
        select(Asset.asset_id).where(Asset.symbol == symbol)
    ).scalar_one()


def new_payment(connection: Connection, portfolio_id: uuid.UUID) -> uuid.UUID:
    return connection.execute(
        insert(BalanceChange)
        .values(
            portfolio_id=portfolio_id,
            amount=Decimal("-101.5"),
            reason="trade_purchase",
        )
        .returning(BalanceChange.balance_change_id)
    ).scalar_one()


def new_trade(
    connection: Connection, portfolio: uuid.UUID, **values: object
) -> uuid.UUID:
    """A good trade of 1 AAPL at 101.5 for portfolio, paid for by a new
    payment from it, changed by values."""
    row: dict[str, object] = {
        "request_id": uuid.uuid4(),
        "portfolio_id": portfolio,
        "asset_id": asset_id(connection),
        "trade_type": "buy",
        "quantity": 1,
        "unit_price": Decimal("101.5"),
        "currency_amount": Decimal("101.5"),
        "cash_balance_after": Decimal("398.5"),
        "status": "executed",
        "created_at": AT,
        **values,
    }
    if "balance_change_id" not in row:
        row["balance_change_id"] = new_payment(connection, portfolio)
    return connection.execute(
        insert(Trade).values(**row).returning(Trade.trade_id)
    ).scalar_one()


def add_holding(
    connection: Connection,
    portfolio_id: uuid.UUID,
    quantity: int,
    symbol: str = "AAPL",
) -> None:
    connection.execute(
        insert(Holding).values(
            portfolio_id=portfolio_id,
            asset_id=asset_id(connection, symbol),
            quantity=quantity,
        )
    )


@pytest.mark.parametrize(
    "unit_price",
    [
        pytest.param(Decimal("0.0001"), id="lowest"),
        # The highest price the prices table holds.
        pytest.param(Decimal("99999999.9999"), id="highest"),
    ],
)
def test_the_lowest_and_highest_prices_and_a_zero_balance_are_allowed(
    connection: Connection, unit_price: Decimal
) -> None:
    new_trade(
        connection,
        new_portfolio(connection),
        unit_price=unit_price,
        currency_amount=unit_price,
        cash_balance_after=Decimal(0),
    )


@pytest.mark.parametrize(
    ("values", "rule"),
    [
        # Each case keeps currency_amount = quantity × unit_price unless
        # that is the rule being tested, so only one rule can fail.
        (
            {"quantity": 0, "currency_amount": Decimal(0)},
            "quantity_positive",
        ),
        (
            {"quantity": -1, "currency_amount": Decimal("-101.5")},
            "quantity_positive",
        ),
        (
            {"unit_price": Decimal(0), "currency_amount": Decimal(0)},
            "unit_price_positive",
        ),
        (
            {"unit_price": Decimal(-1), "currency_amount": Decimal(-1)},
            "unit_price_positive",
        ),
        (
            {"unit_price": Decimal("NaN"), "currency_amount": Decimal("NaN")},
            "unit_price_positive",
        ),
        # The cost is exactly quantity × price, never less and never more.
        ({"currency_amount": Decimal("101.4999")}, "amount_matches"),
        ({"currency_amount": Decimal("101.5001")}, "amount_matches"),
        ({"quantity": 2}, "amount_matches"),
        (
            {"cash_balance_after": Decimal("-0.0001")},
            "cash_balance_after_not_negative",
        ),
        (
            {"cash_balance_after": Decimal("NaN")},
            "cash_balance_after_not_negative",
        ),
        # Only buying, and only trades that happened, for now.
        ({"trade_type": "sell"}, "trade_type_valid"),
        ({"status": "queued"}, "status_valid"),
    ],
)
def test_bad_trades_are_refused(
    connection: Connection, values: dict[str, object], rule: str
) -> None:
    portfolio_id = new_portfolio(connection)

    with pytest.raises(IntegrityError, match=rule):
        new_trade(connection, portfolio_id, **values)


def test_a_request_id_makes_one_trade_per_portfolio(
    connection: Connection,
) -> None:
    request_id = uuid.uuid4()
    portfolio_id = new_portfolio(connection)
    new_trade(connection, portfolio_id, request_id=request_id)
    # Another user's phone may make the same ID.
    new_trade(connection, new_portfolio(connection), request_id=request_id)

    with pytest.raises(
        IntegrityError, match="uq_trades_portfolio_id_request_id"
    ):
        new_trade(connection, portfolio_id, request_id=request_id)


def test_one_payment_pays_for_one_trade(connection: Connection) -> None:
    portfolio_id = new_portfolio(connection)
    payment = new_payment(connection, portfolio_id)
    new_trade(connection, portfolio_id, balance_change_id=payment)

    with pytest.raises(IntegrityError, match="uq_trades_balance_change_id"):
        new_trade(connection, portfolio_id, balance_change_id=payment)


def test_a_trade_needs_a_real_stock(connection: Connection) -> None:
    # The cascade and cannot-delete tests below check the other two
    # foreign keys.
    portfolio_id = new_portfolio(connection)

    with pytest.raises(IntegrityError, match="fk_trades_asset_id_assets"):
        new_trade(connection, portfolio_id, asset_id=uuid.uuid4())


def test_a_trades_payment_cannot_be_deleted_on_its_own(
    connection: Connection,
) -> None:
    portfolio_id = new_portfolio(connection)
    payment = new_payment(connection, portfolio_id)
    new_trade(connection, portfolio_id, balance_change_id=payment)

    with pytest.raises(
        IntegrityError, match="fk_trades_balance_change_id_balance_changes"
    ):
        connection.execute(
            delete(BalanceChange).where(
                BalanceChange.balance_change_id == payment
            )
        )


def test_a_holding_needs_a_real_stock(connection: Connection) -> None:
    with pytest.raises(IntegrityError, match="fk_holdings_asset_id_assets"):
        connection.execute(
            insert(Holding).values(
                portfolio_id=new_portfolio(connection),
                asset_id=uuid.uuid4(),
                quantity=1,
            )
        )


def test_a_holding_can_be_zero_but_never_below(connection: Connection) -> None:
    portfolio_id = new_portfolio(connection)
    add_holding(connection, portfolio_id, 0)

    with pytest.raises(IntegrityError, match="quantity_not_negative"):
        add_holding(connection, portfolio_id, -1, symbol="MSFT")


def count(connection: Connection, table: type, portfolio_id: uuid.UUID) -> int:
    return connection.execute(
        select(func.count()).where(table.portfolio_id == portfolio_id)
    ).scalar_one()


def test_delete_portfolio_removes_its_trades_and_holdings(
    db_session: Session,
) -> None:
    # The demo reset uses delete_portfolio, so this is what it relies on.
    connection = db_session.connection()
    gone, kept = new_portfolio(connection), new_portfolio(connection)
    for portfolio_id in (gone, kept):
        new_trade(connection, portfolio_id)
        add_holding(connection, portfolio_id, 1)

    delete_portfolio(db_session, gone)

    for table in (Trade, Holding, BalanceChange):
        assert count(connection, table, gone) == 0
        assert count(connection, table, kept) == 1
