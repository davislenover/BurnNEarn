"""Tests for GET /v1/assets and GET /v1/market/usage."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.main import app
from app.market.models import Asset, Price, ProviderRequest, RequestOutcome
from app.market.providers.settings import (
    ProviderSettings,
    get_provider_settings,
)

# Tuesday Nov 10, 2026 at 10:00 in New York: the market is open.
OPEN = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
# Saturday Nov 14, 2026 at 10:00 in New York: the market is closed.
CLOSED = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)

# at_time and add_price are fixtures in conftest.py, shared with the
# modules that need prices.
SetTime = Callable[[datetime], None]
AddPrice = Callable[[str, str, datetime], None]


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
    client: TestClient,
    db_session: Session,
    add_price: AddPrice,
    at_time: SetTime,
) -> None:
    at_time(OPEN)
    add_price("AAPL", "101.5", OPEN - timedelta(seconds=20))

    aapl = by_symbol(client.get("/v1/assets").json())["AAPL"]

    assert aapl["price"] == "101.5000"
    assert datetime.fromisoformat(aapl["quoted_at"]) == OPEN - timedelta(
        seconds=20
    )
    # When the database saved it, not the quote time.
    obtained_at = db_session.scalars(select(Price.obtained_at)).one()
    assert datetime.fromisoformat(aapl["obtained_at"]) == obtained_at
    assert aapl["delayed"] is False


def test_an_old_price_is_delayed_while_the_market_is_open(
    client: TestClient, add_price: AddPrice, at_time: SetTime
) -> None:
    at_time(OPEN)
    add_price("AAPL", "100", OPEN - timedelta(minutes=16))

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


def use_provider(**values: object) -> None:
    """Make the routes see these provider settings. The client undoes it."""
    app.dependency_overrides[get_provider_settings] = lambda: ProviderSettings(
        _env_file=None, **values
    )


def test_usage_counts_the_calls_to_the_provider(
    client: TestClient, db_session: Session, at_time: SetTime
) -> None:
    at_time(OPEN)
    use_provider(market_provider="finnhub", finnhub_api_key="not-real")
    times = [
        # 2 in the last minute
        OPEN - timedelta(seconds=10),
        OPEN - timedelta(seconds=30),
        # 1 just before it
        OPEN - timedelta(seconds=90),
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
        "calls_today": 6,
        # Finnhub's limit, since it is the chosen provider.
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
    # conftest.py chooses the fake provider, which has no limit.
    assert usage["limit_per_minute"] is None
