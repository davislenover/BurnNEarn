"""Tests for what a portfolio is worth: portfolio_value and
GET /v1/me/portfolio."""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market.models import Asset, Price
from app.trading.models import Holding
from app.trading.service import portfolio_value
from app.users.interface import create_user
from app.users.types import CurrentUser
from app.wallet.interface import (
    change_balance,
    create_live_portfolio,
    lock_live_portfolio,
)
from app.wallet.types import BalanceChangeReason

# The fixtures' types. They are defined in conftest.py, which tests don't
# import.
AddPrice = Callable[[str, str, datetime], None]
MakePortfolio = Callable[..., Any]
AsUser = Callable[[CurrentUser], None]
SetTime = Callable[[datetime], None]

# Monday, Nov 9, 2026 at 10:00 in New York, while the market is open.
NOW = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)
A_MINUTE_AGO = NOW - timedelta(minutes=1)
# The same day at 16:30 in New York, after the close.
CLOSED = datetime(2026, 11, 9, 21, 30, tzinfo=UTC)


@pytest.fixture
def session(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """db_session, but a commit fails the test. portfolio_value only
    reads."""

    def no_commit() -> None:
        raise AssertionError("portfolio_value must never commit")

    monkeypatch.setattr(db_session, "commit", no_commit)
    return db_session


def portfolio(session: Session, balance: str) -> uuid.UUID:
    """A new user's live portfolio with this balance."""
    user_id = create_user(session)
    portfolio_id = create_live_portfolio(session, user_id)
    if Decimal(balance) > 0:
        change_balance(
            session,
            lock_live_portfolio(session, user_id),
            Decimal(balance),
            BalanceChangeReason.ACTIVITY_REWARD,
            date(2026, 11, 8),
        )
    return portfolio_id


def asset_id(session: Session, symbol: str) -> uuid.UUID:
    return session.execute(
        select(Asset.asset_id).where(Asset.symbol == symbol)
    ).scalar_one()


def price(
    session: Session,
    symbol: str,
    value: str,
    quoted_at: datetime = A_MINUTE_AGO,
    obtained_at: datetime | None = None,
) -> None:
    """A price for symbol. Without obtained_at, the database sets it."""
    times = {"quoted_at": quoted_at}
    if obtained_at is not None:
        times["obtained_at"] = obtained_at
    session.add(
        Price(
            asset_id=asset_id(session, symbol), price=Decimal(value), **times
        )
    )
    session.flush()


def hold(
    session: Session, portfolio_id: uuid.UUID, symbol: str, quantity: int
) -> None:
    session.add(
        Holding(
            portfolio_id=portfolio_id,
            asset_id=asset_id(session, symbol),
            quantity=quantity,
        )
    )
    session.flush()


def test_each_holding_is_quantity_times_its_latest_price(
    session: Session,
) -> None:
    portfolio_id = portfolio(session, "398.5")
    # Symbol order (AAPL first) differs from the order they are added in,
    # and from the order of their quantities, prices and values.
    hold(session, portfolio_id, "MSFT", 2)
    hold(session, portfolio_id, "AAPL", 3)
    price(session, "MSFT", "40.1234")
    price(session, "AAPL", "30", quoted_at=NOW - timedelta(minutes=5))
    # Got a little after the provider set it, so the two times differ.
    price(session, "AAPL", "433.3333", obtained_at=NOW - timedelta(seconds=10))

    value = portfolio_value(session, portfolio_id, NOW)

    assert [h.symbol for h in value.holdings] == ["AAPL", "MSFT"]
    aapl, msft = value.holdings
    assert aapl.quantity == 3
    assert aapl.price == Decimal("433.3333")
    assert aapl.quoted_at == A_MINUTE_AGO
    assert aapl.obtained_at == NOW - timedelta(seconds=10)
    assert not aapl.delayed
    assert aapl.value == Decimal("1299.9999")
    assert msft.value == Decimal("80.2468")
    # Exact, to the last of 4 decimals.
    assert value.cash_balance == Decimal("398.5")
    assert value.holdings_value == Decimal("1380.2467")
    assert value.total_value == Decimal("1778.7467")


def test_a_delayed_price_is_still_used_and_flagged(session: Session) -> None:
    portfolio_id = portfolio(session, "0")
    hold(session, portfolio_id, "AAPL", 2)
    price(session, "AAPL", "101.5", quoted_at=NOW - timedelta(minutes=20))

    (aapl,) = portfolio_value(session, portfolio_id, NOW).holdings

    assert aapl.delayed
    assert aapl.value == Decimal("203")


def test_after_the_close_the_last_price_is_not_delayed(
    session: Session,
) -> None:
    portfolio_id = portfolio(session, "0")
    hold(session, portfolio_id, "AAPL", 1)
    price(session, "AAPL", "101.5", quoted_at=NOW)

    (aapl,) = portfolio_value(session, portfolio_id, CLOSED).holdings

    assert not aapl.delayed


@pytest.fixture
def owner(
    make_portfolio: MakePortfolio,
    add_price: AddPrice,
    as_user: AsUser,
    at_time: SetTime,
) -> Any:
    """A user with 500 whose requests the routes see, AAPL at 101.5 and
    the time set to NOW."""
    made = make_portfolio(Decimal("500"))
    as_user(made.user)
    at_time(NOW)
    add_price("AAPL", "101.5", A_MINUTE_AGO)
    return made


def test_a_buy_shows_in_the_portfolio(
    client: TestClient, db_session: Session, owner: Any
) -> None:
    client.post(
        "/v1/me/trades",
        json={
            "request_id": str(uuid.uuid4()),
            "symbol": "AAPL",
            "trade_type": "buy",
            "quantity": 2,
            "expected_price": "101.5",
        },
    )

    response = client.get("/v1/me/portfolio")

    assert response.status_code == 200
    reply = response.json()
    (aapl,) = reply["holdings"]
    assert datetime.fromisoformat(aapl.pop("quoted_at")) == A_MINUTE_AGO
    # The database set obtained_at when owner added the price.
    obtained = db_session.scalar(
        select(Price.obtained_at).join(Asset).where(Asset.symbol == "AAPL")
    )
    assert datetime.fromisoformat(aapl.pop("obtained_at")) == obtained
    assert aapl == {
        "symbol": "AAPL",
        "quantity": 2,
        "price": "101.5000",
        "delayed": False,
        "value": "203.0000",
    }
    assert reply["cash_balance"] == "297.0000"
    assert reply["holdings_value"] == "203.0000"
    assert reply["total_value"] == "500.0000"
    assert reply["simulated"] is True


def test_a_new_users_portfolio_is_empty(
    client: TestClient, owner: Any
) -> None:
    response = client.get("/v1/me/portfolio")

    assert response.json() == {
        "cash_balance": "500.0000",
        "holdings": [],
        "holdings_value": "0.0000",
        "total_value": "500.0000",
        "simulated": True,
    }


def test_the_portfolio_is_the_current_users(
    client: TestClient,
    db_session: Session,
    make_portfolio: MakePortfolio,
    as_user: AsUser,
    at_time: SetTime,
    add_price: AddPrice,
) -> None:
    # Another user, made first, with their own cash and shares.
    other = make_portfolio(Decimal("77"))
    hold(db_session, other.portfolio_id, "AAPL", 5)
    db_session.commit()
    mine = make_portfolio(Decimal("500"))
    as_user(mine.user)
    at_time(NOW)
    add_price("AAPL", "101.5", A_MINUTE_AGO)

    reply = client.get("/v1/me/portfolio").json()

    assert reply["cash_balance"] == "500.0000"
    assert reply["holdings"] == []


def test_the_docs_say_simulated_is_always_sent_and_true(
    client: TestClient,
) -> None:
    schema = client.get("/openapi.json").json()

    reply = schema["components"]["schemas"]["PortfolioReply"]
    assert "simulated" in reply["required"]
    assert reply["properties"]["simulated"]["const"] is True


def test_the_portfolio_with_no_current_user_is_a_401(
    client: TestClient, make_portfolio: MakePortfolio
) -> None:
    # conftest turns the demo user off, and no as_user picks a user.
    make_portfolio(Decimal("500"))

    response = client.get("/v1/me/portfolio")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"
