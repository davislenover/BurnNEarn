"""The market module's settings, read from environment variables or .env."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MarketSettings(BaseSettings):
    """Each field is set by the environment variable of the same name in
    upper case, for example MARKET_PROVIDER."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where prices come from: Finnhub, or made-up prices that need no key.
    market_provider: Literal["finnhub", "fake"] = "fake"
    # Kept on the server only, never sent to the app (HA SEC-33).
    finnhub_api_key: SecretStr | None = None
    # Treat the market as open at any time, for development in the evening.
    # Only allowed with the fake provider, so real prices are never shown as
    # live when the market is closed.
    market_always_open: bool = False
    # Start the price poller with the app. Off by default, and off in tests.
    market_poller_enabled: bool = False

    @model_validator(mode="after")
    def check_combination(self) -> Self:
        """Refuse settings that can't work, when they load, instead of
        failing later."""
        key = self.finnhub_api_key
        if self.market_provider == "finnhub" and not (
            key and key.get_secret_value()
        ):
            raise ValueError("MARKET_PROVIDER=finnhub needs FINNHUB_API_KEY")
        if self.market_always_open and self.market_provider != "fake":
            raise ValueError(
                "MARKET_ALWAYS_OPEN only works with MARKET_PROVIDER=fake"
            )
        return self


@lru_cache
def get_market_settings() -> MarketSettings:
    """Return the market settings, read once per process."""
    return MarketSettings()
