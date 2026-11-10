"""Where market prices come from.

Every provider has the same shape, MarketDataProvider in base.py, so the rest
of the market module never knows which one it is using:
- FinnhubProvider is an adapter: it turns Finnhub's API into a Quote.
- FakeProvider makes up prices, for development and tests.

build_provider picks one from the MARKET_PROVIDER setting, and
provider_type says which one without making it. To add a provider:
1. Write a class in this folder that names MarketDataProvider as its base,
   with get_quote(symbol) and calls_per_minute.
2. Add its name to MARKET_PROVIDER in settings.py in this folder, and to
   .env.example.
3. Add it to PROVIDERS below, and to build_provider if it needs settings to
   be made.
"""

from app.market.providers.base import MarketDataProvider
from app.market.providers.fake import FakeProvider
from app.market.providers.finnhub import FinnhubProvider
from app.market.providers.settings import ProviderSettings

# Each provider by its MARKET_PROVIDER name.
PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "finnhub": FinnhubProvider,
    "fake": FakeProvider,
}


def provider_type(settings: ProviderSettings) -> type[MarketDataProvider]:
    """Return the class of the provider that MARKET_PROVIDER names, so its
    request limit can be read without making one."""
    try:
        return PROVIDERS[settings.market_provider]
    except KeyError:
        # Never fall back to made-up prices, which would be shown as real.
        raise ValueError(
            f"Unknown MARKET_PROVIDER: {settings.market_provider}"
        ) from None


def build_provider(settings: ProviderSettings) -> MarketDataProvider:
    """Return the provider that MARKET_PROVIDER names."""
    kind = provider_type(settings)
    if kind is FinnhubProvider:
        # ProviderSettings refuses to load without a key for Finnhub.
        assert settings.finnhub_api_key is not None
        return FinnhubProvider(settings.finnhub_api_key)
    if kind is FakeProvider:
        return FakeProvider()
    raise ValueError(f"build_provider can't make {kind.__name__} yet")
