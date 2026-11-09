"""Tests for poll_once, which saves a quote for every tradable asset."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.market.models import Asset, Price, ProviderRequest, RequestOutcome
from app.market.poller import poll_once
from app.market.providers.base import (
    MarketDataError,
    Quote,
    RateLimitedError,
    UnknownSymbolError,
)
from app.market.providers.fake import FakeProvider

NOW = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
QUOTED_AT = NOW - timedelta(seconds=20)


class StubProvider:
    """Answers with fixed prices, or raises the error set for a symbol."""

    def __init__(
        self,
        price: Decimal = Decimal("100"),
        errors: dict[str, Exception] | None = None,
        rate_limit_after: int | None = None,
    ) -> None:
        self.price = price
        self.errors = errors or {}
        self.rate_limit_after = rate_limit_after
        self.calls: list[str] = []

    def get_quote(self, symbol: str) -> Quote:
        self.calls.append(symbol)
        if (
            self.rate_limit_after is not None
            and len(self.calls) > self.rate_limit_after
        ):
            raise RateLimitedError("limit")
        if symbol in self.errors:
            raise self.errors[symbol]
        return Quote(symbol=symbol, price=self.price, quoted_at=QUOTED_AT)


def tradable_symbols(session: Session) -> list[str]:
    return list(
        session.scalars(
            select(Asset.symbol)
            .where(Asset.is_tradable)
            .order_by(Asset.symbol)
        )
    )


def saved_symbols(session: Session) -> list[str]:
    return list(
        session.scalars(
            select(Asset.symbol)
            .join(Price, Price.asset_id == Asset.asset_id)
            .order_by(Asset.symbol)
        )
    )


def outcomes(session: Session) -> dict[str, str]:
    rows = session.execute(
        select(ProviderRequest.symbol, ProviderRequest.outcome)
    )
    return {symbol: outcome for symbol, outcome in rows}


def test_the_fake_provider_gives_every_tradable_asset_a_price(
    db_session: Session,
) -> None:
    saved_all = poll_once(db_session, FakeProvider(clock=lambda: NOW), NOW)

    assert saved_all is True
    symbols = tradable_symbols(db_session)
    assert saved_symbols(db_session) == symbols
    assert outcomes(db_session) == dict.fromkeys(symbols, RequestOutcome.OK)


def test_an_asset_that_is_not_tradable_is_not_asked_for(
    db_session: Session,
) -> None:
    db_session.execute(
        update(Asset).where(Asset.symbol == "AAPL").values(is_tradable=False)
    )
    provider = StubProvider()

    poll_once(db_session, provider, NOW)

    assert "AAPL" not in provider.calls
    assert "AAPL" not in saved_symbols(db_session)


def test_one_failing_asset_does_not_stop_the_others(
    db_session: Session,
) -> None:
    provider = StubProvider(
        errors={
            "AAPL": MarketDataError("timeout"),
            "MSFT": UnknownSymbolError("no price"),
        }
    )

    saved_all = poll_once(db_session, provider, NOW)

    assert saved_all is False
    others = [
        s for s in tradable_symbols(db_session) if s not in {"AAPL", "MSFT"}
    ]
    assert saved_symbols(db_session) == others
    assert outcomes(db_session)["AAPL"] == RequestOutcome.ERROR
    assert outcomes(db_session)["MSFT"] == RequestOutcome.UNKNOWN_SYMBOL


def test_the_request_limit_stops_the_poll(db_session: Session) -> None:
    provider = StubProvider(rate_limit_after=2)

    saved_all = poll_once(db_session, provider, NOW)

    assert saved_all is False
    first_three = tradable_symbols(db_session)[:3]
    assert provider.calls == first_three
    assert saved_symbols(db_session) == first_three[:2]
    assert outcomes(db_session)[first_three[2]] == (
        RequestOutcome.RATE_LIMITED
    )


def test_the_same_quote_is_saved_once(db_session: Session) -> None:
    poll_once(db_session, StubProvider(), NOW)
    poll_once(db_session, StubProvider(), NOW + timedelta(minutes=1))

    count = db_session.scalar(select(func.count()).select_from(Price))
    assert count == len(tradable_symbols(db_session))


def test_a_corrected_price_replaces_the_stored_one(
    db_session: Session,
) -> None:
    poll_once(db_session, StubProvider(price=Decimal("100")), NOW)
    poll_once(db_session, StubProvider(price=Decimal("101.5")), NOW)

    prices = set(db_session.scalars(select(Price.price)))
    assert prices == {Decimal("101.5")}


def test_every_call_is_recorded_at_the_poll_time(db_session: Session) -> None:
    poll_once(db_session, StubProvider(), NOW)

    times = set(db_session.scalars(select(ProviderRequest.requested_at)))
    assert times == {NOW}


def test_a_call_is_recorded_only_with_a_known_outcome(
    db_session: Session,
) -> None:
    db_session.add(
        ProviderRequest(requested_at=NOW, symbol="AAPL", outcome="timeout")
    )

    with pytest.raises(IntegrityError, match="outcome_valid"):
        db_session.flush()


def test_a_quote_the_database_refuses_undoes_only_itself(
    db_session: Session,
) -> None:
    class ZeroForAapl(StubProvider):
        def get_quote(self, symbol: str) -> Quote:
            quote = super().get_quote(symbol)
            if symbol == "AAPL":
                # Breaks the rule that a price is above 0.
                return Quote(symbol, Decimal("0"), quote.quoted_at)
            return quote

    saved_all = poll_once(db_session, ZeroForAapl(), NOW)

    assert saved_all is False
    others = [s for s in tradable_symbols(db_session) if s != "AAPL"]
    assert saved_symbols(db_session) == others
    assert outcomes(db_session)["AAPL"] == RequestOutcome.OK


@pytest.mark.parametrize(
    "error", [MarketDataError("down"), UnknownSymbolError("no price")]
)
def test_one_missed_price_fails_the_poll(
    db_session: Session, error: Exception
) -> None:
    # A provider that is down, or a wrong key, fails every symbol like this.
    provider = StubProvider(errors={"AAPL": error})

    assert poll_once(db_session, provider, NOW) is False
