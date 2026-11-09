"""The market module's settings, read from environment variables or .env.

The provider settings (MARKET_PROVIDER and FINNHUB_API_KEY) live with the
providers, in app/market/providers/settings.py.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.market.providers.settings import ProviderSettings


class MarketSettings(BaseSettings):
    """Each field is set by the environment variable of the same name in
    upper case, for example MARKET_ALWAYS_OPEN."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Treat the market as open at any time, for development in the evening.
    # Only allowed with the fake provider, see check_always_open.
    market_always_open: bool = False
    # Start the price poller with the app. Off by default, and off in tests.
    market_poller_enabled: bool = False


def check_always_open(
    market: MarketSettings, providers: ProviderSettings
) -> None:
    """Refuse MARKET_ALWAYS_OPEN with a real provider, so real prices are
    never shown as live while the market is closed. Runs when the app
    starts."""
    if market.market_always_open and providers.market_provider != "fake":
        raise ValueError(
            "MARKET_ALWAYS_OPEN only works with MARKET_PROVIDER=fake"
        )


@lru_cache
def get_market_settings() -> MarketSettings:
    """Return the market settings, read once per process."""
    return MarketSettings()
