"""Tests for POST /v1/me/trades."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.trading.models import Holding, Trade
from app.users.types import CurrentUser
from app.wallet.queries import get_balance

# The fixtures' types. They are defined in conftest.py, which tests don't
# import.
AddPrice = Callable[[str, str, datetime], None]
MakePortfolio = Callable[..., Any]
AsUser = Callable[[CurrentUser], None]
SetTime = Callable[[datetime], None]

# Monday, Nov 9, 2026 at 10:00 in New York, while the market is open.
NOW = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)
# The same day at 16:30 in New York, after the close.
CLOSED = datetime(2026, 11, 9, 21, 30, tzinfo=UTC)


def body(**changes: object) -> dict[str, object]:
    """A buy of 1 AAPL at 101.5 with a new request_id, changed by changes."""
    return {
        "request_id": str(uuid.uuid4()),
        "symbol": "AAPL",
        "trade_type": "buy",
        "quantity": 1,
        "expected_price": "101.5",
        **changes,
    }


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
    add_price("AAPL", "101.5", NOW - timedelta(minutes=1))
    return made


def trades(db_session: Session, portfolio_id: uuid.UUID) -> int:
    return db_session.execute(
        select(func.count()).where(Trade.portfolio_id == portfolio_id)
    ).scalar_one()


def holdings(db_session: Session, portfolio_id: uuid.UUID) -> int:
    return db_session.execute(
        select(func.coalesce(func.sum(Holding.quantity), 0)).where(
            Holding.portfolio_id == portfolio_id
        )
    ).scalar_one()


def test_a_buy_is_201_and_a_repeat_is_200_with_the_same_body(
    client: TestClient, db_session: Session, owner: Any, at_time: SetTime
) -> None:
    # PostgreSQL gives stored times back in the session's time zone. With
    # one that isn't UTC, the repeat only matches if the reply converts.
    db_session.execute(text("SET TIME ZONE 'America/Toronto'"))
    db_session.commit()
    # The price as GET /v1/assets gives it. Other tests send 101.5, so
    # together they show the price is compared as a number, not as text.
    sent = body(quantity=2, expected_price="101.5000")

    first = client.post("/v1/me/trades", json=sent)
    # Another buy changes the balance, and the repeat comes 5 minutes
    # later, so it only matches if it is built from the first trade.
    client.post("/v1/me/trades", json=body())
    at_time(NOW + timedelta(minutes=5))
    again = client.post("/v1/me/trades", json=sent)

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json() == first.json()
    reply = first.json()
    uuid.UUID(reply.pop("trade_id"))
    assert reply == {
        "status": "executed",
        "unit_price": "101.5000",
        "currency_amount": "203.0000",
        "executed_at": "2026-11-09T15:00:00Z",
        "cash_balance": "297.0000",
    }


@pytest.mark.parametrize(
    ("changes", "status", "code"),
    [
        pytest.param({"symbol": "ZZZZ"}, 404, "unknown_asset", id="unknown"),
        pytest.param({"quantity": 5}, 409, "insufficient_funds", id="poor"),
    ],
)
def test_a_refused_buy_is_sent_as_its_code_and_saves_nothing(
    client: TestClient,
    db_session: Session,
    owner: Any,
    changes: dict[str, object],
    status: int,
    code: str,
) -> None:
    response = client.post("/v1/me/trades", json=body(**changes))

    assert response.status_code == status
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert detail["message"]
    assert get_balance(db_session, owner.portfolio_id) == Decimal("500")
    assert trades(db_session, owner.portfolio_id) == 0
    assert holdings(db_session, owner.portfolio_id) == 0


def test_a_closed_market_is_refused(
    client: TestClient, owner: Any, at_time: SetTime
) -> None:
    at_time(CLOSED)

    response = client.post("/v1/me/trades", json=body())

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "market_closed",
        "message": "The market is closed. Try again when it opens.",
    }


def test_a_delayed_price_is_refused(
    client: TestClient, owner: Any, add_price: AddPrice
) -> None:
    # MSFT's only price is 20 minutes old, while the market is open.
    add_price("MSFT", "400", NOW - timedelta(minutes=20))

    response = client.post(
        "/v1/me/trades", json=body(symbol="MSFT", expected_price="400")
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "price_out_of_date",
        "message": (
            "This stock's price is out of date, so it can't be bought "
            "right now."
        ),
    }


def test_a_reused_request_id_is_refused(
    client: TestClient, db_session: Session, owner: Any
) -> None:
    sent = body()
    client.post("/v1/me/trades", json=sent)

    response = client.post("/v1/me/trades", json={**sent, "quantity": 2})

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "request_id_reused",
        "message": "This request ID was already used for a different trade.",
    }
    assert trades(db_session, owner.portfolio_id) == 1


def test_the_same_buy_with_a_new_request_id_is_a_second_trade(
    client: TestClient, db_session: Session, owner: Any
) -> None:
    # Only the request_id makes a repeat. A second, identical buy that the
    # user confirmed again is a new trade (VnV test-mkt-13).
    sent = body()
    first = client.post("/v1/me/trades", json=sent)
    client.post("/v1/me/trades", json=sent)

    second = client.post(
        "/v1/me/trades", json={**sent, "request_id": str(uuid.uuid4())}
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["trade_id"] != first.json()["trade_id"]
    assert trades(db_session, owner.portfolio_id) == 2
    assert holdings(db_session, owner.portfolio_id) == 2
    assert get_balance(db_session, owner.portfolio_id) == Decimal("297")


def test_a_new_request_at_an_old_price_gets_the_new_price(
    client: TestClient, owner: Any, add_price: AddPrice, at_time: SetTime
) -> None:
    # SEC-29, after an earlier buy at that price: the earlier trade doesn't
    # make the new request a repeat.
    client.post("/v1/me/trades", json=body())
    add_price("AAPL", "105", NOW + timedelta(minutes=1))
    at_time(NOW + timedelta(minutes=2))

    response = client.post("/v1/me/trades", json=body())

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "price_changed"
    assert "105.0000" in detail["message"]


def test_the_phone_cannot_name_a_user(
    client: TestClient, db_session: Session, owner: Any
) -> None:
    # The user comes from get_current_user, so a body that names one is
    # refused. The request tests check each other field that doesn't fit.
    response = client.post(
        "/v1/me/trades", json=body(user_id=str(uuid.uuid4()))
    )

    assert response.status_code == 422
    assert trades(db_session, owner.portfolio_id) == 0


def test_a_buy_with_no_current_user_is_a_401(
    client: TestClient, make_portfolio: MakePortfolio, at_time: SetTime
) -> None:
    # conftest turns the demo user off, and no as_user picks a user.
    make_portfolio(Decimal("500"))
    at_time(NOW)

    response = client.post("/v1/me/trades", json=body())

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "code": "not_authenticated",
            "message": "Sign in to continue.",
        }
    }


def test_a_buy_that_fails_halfway_saves_nothing_and_can_be_sent_again(
    client: TestClient,
    db_session: Session,
    owner: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # FR_MktAtomicTrade: adding the shares fails after the payment is
    # written, so the route never commits.
    def fail(*args: object) -> None:
        raise RuntimeError("adding the shares failed")

    sent = body()
    with monkeypatch.context() as patch:
        patch.setattr("app.trading.service._add_shares", fail)
        with pytest.raises(RuntimeError):
            client.post("/v1/me/trades", json=sent)

    assert get_balance(db_session, owner.portfolio_id) == Decimal("500")
    assert trades(db_session, owner.portfolio_id) == 0
    assert holdings(db_session, owner.portfolio_id) == 0

    response = client.post("/v1/me/trades", json=sent)

    assert response.status_code == 201
    assert trades(db_session, owner.portfolio_id) == 1
    assert get_balance(db_session, owner.portfolio_id) == Decimal("398.5")
