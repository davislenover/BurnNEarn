"""Tests for the Finnhub client, using a fake Finnhub (no network, no key)."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import httpx2
import pytest
from pydantic import SecretStr

from app.market.finnhub import FINNHUB_BASE_URL, FinnhubProvider
from app.market.provider import (
    MarketDataError,
    RateLimitedError,
    UnknownSymbolError,
)

FAKE_KEY = "test-key-not-real"


def provider_answering(
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> FinnhubProvider:
    """A FinnhubProvider whose requests go to handler instead of Finnhub."""
    client = httpx2.Client(
        base_url=FINNHUB_BASE_URL, transport=httpx2.MockTransport(handler)
    )
    return FinnhubProvider(SecretStr(FAKE_KEY), client=client)


def test_reads_price_and_quote_time_exactly() -> None:
    provider = provider_answering(
        lambda request: httpx2.Response(
            200, text='{"c": 342.88, "pc": 347.725, "t": 1793040139}'
        )
    )

    quote = provider.get_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.price == Decimal("342.88")
    assert quote.quoted_at == datetime(2026, 10, 26, 18, 42, 19, tzinfo=UTC)


def test_sends_only_the_symbol_and_keeps_the_key_out_of_the_url() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, text='{"c": 1.5, "t": 1793040139}')

    provider_answering(handler).get_quote("MSFT")

    request = seen[0]
    assert request.url.path == "/api/v1/quote"
    assert dict(request.url.params) == {"symbol": "MSFT"}
    assert FAKE_KEY not in str(request.url)
    assert request.headers["X-Finnhub-Token"] == FAKE_KEY


def test_unknown_symbol_is_reported() -> None:
    provider = provider_answering(
        lambda request: httpx2.Response(200, text='{"c": 0, "t": 0}')
    )

    with pytest.raises(UnknownSymbolError):
        provider.get_quote("NOTREAL")


def test_request_limit_is_reported() -> None:
    provider = provider_answering(lambda request: httpx2.Response(429))

    with pytest.raises(RateLimitedError):
        provider.get_quote("AAPL")


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(500),
        httpx2.Response(200, text="not json"),
        httpx2.Response(200, text='{"error": "no c or t"}'),
    ],
)
def test_bad_responses_are_reported(response: httpx2.Response) -> None:
    provider = provider_answering(lambda request: response)

    with pytest.raises(MarketDataError):
        provider.get_quote("AAPL")


def test_network_failure_is_reported_without_the_key() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    with pytest.raises(MarketDataError) as error:
        provider_answering(handler).get_quote("AAPL")

    assert FAKE_KEY not in str(error.value)
