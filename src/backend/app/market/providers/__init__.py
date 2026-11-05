"""Where market prices come from.

Every provider has the same shape, MarketDataProvider in base.py, so the rest
of the market module never knows which one it is using:
- FinnhubProvider is an adapter: it turns Finnhub's API into a Quote.
- FakeProvider makes up prices, for development and tests.

build_provider picks one from the MARKET_PROVIDER setting. To add a provider,
write a class with get_quote(symbol) and add it here.
"""

from app.market.providers.base import MarketDataProvider
from app.market.providers.fake import FakeProvider
from app.market.providers.finnhub import FinnhubProvider
from app.market.settings import MarketSettings


def build_provider(settings: MarketSettings) -> MarketDataProvider:
    """Return the provider that MARKET_PROVIDER names."""
    if settings.market_provider == "finnhub":
        # MarketSettings refuses to load without a key for Finnhub.
        assert settings.finnhub_api_key is not None
        return FinnhubProvider(settings.finnhub_api_key)
    return FakeProvider()
