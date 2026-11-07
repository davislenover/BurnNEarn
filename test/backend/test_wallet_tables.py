"""Tests for the portfolios and balance_changes tables (wallet_0001).

These check the rules the database itself keeps, so they hold even for
code that skips wallet's own functions.
"""

import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Connection, delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.db import engine
from app.users.models import User
from app.wallet.models import BalanceChange, Portfolio


@pytest.fixture
def connection(database: None) -> Iterator[Connection]:
    """A connection whose changes are all undone when the test ends."""
    with engine.connect() as connection:
        yield connection
        connection.rollback()


def new_user(connection: Connection) -> uuid.UUID:
    return connection.execute(
        insert(User)
        .values(time_zone="America/Toronto")
        .returning(User.user_id)
    ).scalar_one()


def new_portfolio(connection: Connection, **values: object) -> uuid.UUID:
    values.setdefault("user_id", new_user(connection))
    return connection.execute(
        insert(Portfolio).values(**values).returning(Portfolio.portfolio_id)
    ).scalar_one()


def test_a_portfolio_starts_with_no_currency(connection: Connection) -> None:
    portfolio_id = new_portfolio(connection)

    balance = connection.execute(
        select(Portfolio.cash_balance).where(
            Portfolio.portfolio_id == portfolio_id
        )
    ).scalar_one()
    assert balance == Decimal("0")


@pytest.mark.parametrize("balance", [Decimal("-0.0001"), Decimal("NaN")])
def test_a_balance_can_never_go_below_zero(
    connection: Connection, balance: Decimal
) -> None:
    with pytest.raises(IntegrityError, match="cash_balance_not_negative"):
        new_portfolio(connection, cash_balance=balance)


def test_a_user_has_one_live_portfolio(connection: Connection) -> None:
    user_id = new_user(connection)
    new_portfolio(connection, user_id=user_id)
    # A scenario portfolio is not the live one, so it is allowed.
    new_portfolio(connection, user_id=user_id, scenario_id=uuid.uuid4())

    with pytest.raises(IntegrityError, match="uq_portfolios_live_user_id"):
        new_portfolio(connection, user_id=user_id)


def test_a_portfolio_needs_a_real_user(connection: Connection) -> None:
    with pytest.raises(IntegrityError, match="fk_portfolios_user_id_users"):
        new_portfolio(connection, user_id=uuid.uuid4())


def change(
    connection: Connection, portfolio_id: uuid.UUID, **values: object
) -> None:
    connection.execute(
        insert(BalanceChange).values(portfolio_id=portfolio_id, **values)
    )


@pytest.mark.parametrize(
    ("values", "rule"),
    [
        (
            {"amount": Decimal(0), "reason": "trade_purchase"},
            "amount_not_zero",
        ),
        (
            {"amount": Decimal("NaN"), "reason": "trade_purchase"},
            "amount_not_zero",
        ),
        ({"amount": Decimal(-1), "reason": "gift"}, "reason_valid"),
        # A reward adds currency and a purchase spends it.
        (
            {
                "amount": Decimal(-1),
                "reason": "activity_reward",
                "activity_date": date(2026, 11, 7),
            },
            "amount_sign_matches_reason",
        ),
        (
            {"amount": Decimal(1), "reason": "trade_purchase"},
            "amount_sign_matches_reason",
        ),
        # A reward is for one day of activity, so it needs that day.
        (
            {"amount": Decimal(1), "reason": "activity_reward"},
            "activity_date_only_for_rewards",
        ),
        # Nothing else has an activity day.
        (
            {
                "amount": Decimal(-1),
                "reason": "trade_purchase",
                "activity_date": date(2026, 11, 7),
            },
            "activity_date_only_for_rewards",
        ),
    ],
)
def test_bad_balance_changes_are_refused(
    connection: Connection, values: dict[str, object], rule: str
) -> None:
    portfolio_id = new_portfolio(connection)

    with pytest.raises(IntegrityError, match=rule):
        change(connection, portfolio_id, **values)


def test_deleting_a_portfolio_deletes_its_balance_changes(
    connection: Connection,
) -> None:
    portfolio_id = new_portfolio(connection)
    change(
        connection,
        portfolio_id,
        amount=Decimal("5"),
        reason="activity_reward",
        activity_date=date(2026, 11, 7),
    )

    connection.execute(
        delete(Portfolio).where(Portfolio.portfolio_id == portfolio_id)
    )

    left = connection.execute(
        select(func.count()).where(BalanceChange.portfolio_id == portfolio_id)
    ).scalar_one()
    assert left == 0
