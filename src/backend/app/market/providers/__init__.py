"""Where market prices come from.

Every provider has the same shape, MarketDataProvider in base.py, so the rest
of the market module never knows which one it is using:
- FinnhubProvider is an adapter: it turns Finnhub's API into a Quote.
- FakeProvider makes up prices, for development and tests.

build_provider picks one from the MARKET_PROVIDER setting. To add a provider:
1. Write a class in this folder that names MarketDataProvider as its base and
   has get_quote(symbol).
2. Add its name to MARKET_PROVIDER in settings.py in this folder, and to
   .env.example.
3. Add it to build_provider below.
"""

from app.market.providers.base import MarketDataProvider
from app.market.providers.fake import FakeProvider
from app.market.providers.finnhub import FinnhubProvider
from app.market.providers.settings import ProviderSettings


def build_provider(settings: ProviderSettings) -> MarketDataProvider:
    """Return the provider that MARKET_PROVIDER names."""
    if settings.market_provider == "finnhub":
        # ProviderSettings refuses to load without a key for Finnhub.
        assert settings.finnhub_api_key is not None
        return FinnhubProvider(settings.finnhub_api_key)
    if settings.market_provider == "fake":
        return FakeProvider()
    # Never fall back to made-up prices, which would be shown as real.
    raise ValueError(f"Unknown MARKET_PROVIDER: {settings.market_provider}")
