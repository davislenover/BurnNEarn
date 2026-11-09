"""Tests for choosing a market data provider, and for the fake one."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from app.market.providers import build_provider
from app.market.providers.base import MarketDataProvider
from app.market.providers.fake import MAX_STEP, FakeProvider
from app.market.providers.finnhub import FinnhubProvider
from app.market.providers.settings import ProviderSettings

NOW = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)


def settings(**values: object) -> ProviderSettings:
    """Settings from the values given only, ignoring your own .env."""
    return ProviderSettings(_env_file=None, **values)


def test_the_fake_provider_is_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # conftest.py sets MARKET_PROVIDER for every test. Remove it to see the
    # default.
    monkeypatch.delenv("MARKET_PROVIDER")

    provider = build_provider(settings())

    assert isinstance(provider, FakeProvider)


def test_finnhub_is_used_when_chosen() -> None:
    provider = build_provider(
        settings(market_provider="finnhub", finnhub_api_key="not-real")
    )

    assert isinstance(provider, FinnhubProvider)


def test_an_unknown_provider_name_is_refused() -> None:
    # model_construct skips the checks, as a typo in build_provider would.
    unknown = ProviderSettings.model_construct(market_provider="alpaca")

    with pytest.raises(ValueError, match="alpaca"):
        build_provider(unknown)


def test_a_provider_without_get_quote_fails_when_created() -> None:
    class Forgetful(MarketDataProvider):
        pass

    with pytest.raises(TypeError):
        Forgetful()


def test_finnhub_without_a_key_is_refused() -> None:
    # An empty key is tested where the app starts, in
    # test_market_poller_thread.py.
    with pytest.raises(ValidationError, match="FINNHUB_API_KEY"):
        settings(market_provider="finnhub", finnhub_api_key=None)


def test_the_key_is_hidden_when_printed() -> None:
    loaded = settings(finnhub_api_key=SecretStr("not-real"))

    assert "not-real" not in repr(loaded)


def test_a_fake_symbol_starts_at_the_same_price_at_the_current_time() -> None:
    first = FakeProvider(clock=lambda: NOW).get_quote("AAPL")
    second = FakeProvider(clock=lambda: NOW).get_quote("AAPL")

    assert first.price == second.price
    assert Decimal(20) <= first.price <= Decimal(500)
    assert first.symbol == "AAPL"
    assert first.quoted_at == NOW


def test_a_fake_price_moves_a_little_on_each_call() -> None:
    provider = FakeProvider(clock=lambda: NOW)
    prices = [provider.get_quote("AAPL").price for _ in range(50)]

    for before, after in zip(prices, prices[1:], strict=False):
        assert abs(after - before) <= before * MAX_STEP + Decimal("0.0001")
        assert after > 0
    assert len(set(prices)) > 1
