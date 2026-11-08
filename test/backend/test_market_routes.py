"""Tests for GET /v1/assets and GET /v1/market/usage."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.main import app
from app.market.models import Asset, Price, ProviderRequest, RequestOutcome

# Tuesday Nov 10, 2026 at 10:00 in New York: the market is open.
OPEN = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
# Saturday Nov 14, 2026 at 10:00 in New York: the market is closed.
CLOSED = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)

SetTime = Callable[[datetime], None]


@pytest.fixture
def at_time(client: TestClient) -> Iterator[SetTime]:
    """Set the time routes see: at_time(OPEN)."""

    def set_time(now: datetime) -> None:
        app.dependency_overrides[get_clock] = lambda: lambda: now

    yield set_time


def add_price(
    session: Session, symbol: str, price: str, quoted_at: datetime
) -> None:
    asset_id = session.scalar(
        select(Asset.asset_id).where(Asset.symbol == symbol)
    )
    session.add(
        Price(asset_id=asset_id, price=Decimal(price), quoted_at=quoted_at)
    )
    # Routes only see rows that were committed.
    session.commit()


def by_symbol(body: dict) -> dict[str, dict]:
    return {asset["symbol"]: asset for asset in body["assets"]}


def test_assets_have_no_price_before_the_first_quote(
    client: TestClient, at_time: SetTime
) -> None:
    at_time(OPEN)

    body = client.get("/v1/assets").json()

    assert body["market_open"] is True
    aapl = by_symbol(body)["AAPL"]
    assert aapl == {
        "symbol": "AAPL",
        "name": aapl["name"],
        "price": None,
        "price_currency": "USD",
        "quoted_at": None,
        "obtained_at": None,
        "delayed": False,
    }


def test_an_asset_shows_its_newest_price(
    client: TestClient, db_session: Session, at_time: SetTime
) -> None:
    at_time(OPEN)
    add_price(db_session, "AAPL", "101.5", OPEN - timedelta(seconds=20))

    aapl = by_symbol(client.get("/v1/assets").json())["AAPL"]

    assert aapl["price"] == "101.5000"
    assert datetime.fromisoformat(aapl["quoted_at"]) == OPEN - timedelta(
        seconds=20
    )
    assert aapl["obtained_at"] is not None
    assert aapl["delayed"] is False


def test_an_old_price_is_delayed_while_the_market_is_open(
    client: TestClient, db_session: Session, at_time: SetTime
) -> None:
    at_time(OPEN)
    add_price(db_session, "AAPL", "100", OPEN - timedelta(minutes=16))

    aapl = by_symbol(client.get("/v1/assets").json())["AAPL"]

    assert aapl["delayed"] is True


def test_the_market_is_closed_on_a_saturday(
    client: TestClient, at_time: SetTime
) -> None:
    at_time(CLOSED)

    assert client.get("/v1/assets").json()["market_open"] is False


def test_an_asset_that_is_not_tradable_is_not_listed(
    client: TestClient, db_session: Session, at_time: SetTime
) -> None:
    at_time(OPEN)
    db_session.execute(
        update(Asset).where(Asset.symbol == "AAPL").values(is_tradable=False)
    )
    db_session.commit()

    assert "AAPL" not in by_symbol(client.get("/v1/assets").json())


def test_usage_counts_the_calls_to_the_provider(
    client: TestClient, db_session: Session, at_time: SetTime
) -> None:
    at_time(OPEN)
    times = [
        # 2 in the last minute
        OPEN - timedelta(seconds=10),
        OPEN - timedelta(seconds=30),
        # 3 in one minute earlier today
        OPEN - timedelta(hours=1, seconds=1),
        OPEN - timedelta(hours=1, seconds=2),
        OPEN - timedelta(hours=1, seconds=3),
        # 1 yesterday
        OPEN - timedelta(days=1),
    ]
    db_session.add_all(
        ProviderRequest(
            requested_at=when, symbol="AAPL", outcome=RequestOutcome.OK
        )
        for when in times
    )
    db_session.commit()

    usage = client.get("/v1/market/usage").json()

    assert usage == {
        "calls_last_minute": 2,
        "busiest_minute_today": 3,
        "calls_today": 5,
        "limit_per_minute": 60,
    }


def test_usage_is_zero_before_any_call(
    client: TestClient, at_time: SetTime
) -> None:
    at_time(OPEN)

    usage = client.get("/v1/market/usage").json()

    assert usage["calls_last_minute"] == 0
    assert usage["busiest_minute_today"] == 0
    assert usage["calls_today"] == 0
