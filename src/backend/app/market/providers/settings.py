"""Which market data provider to use, read from environment variables or
.env. Kept with the providers, so changing provider never touches the rest
of market."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseSettings):
    """Each field is set by the environment variable of the same name in
    upper case, for example MARKET_PROVIDER."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where prices come from: Finnhub, or made-up prices that need no key.
    market_provider: Literal["finnhub", "fake"] = "fake"
    # Kept on the server only, never sent to the app (HA SEC-33).
    finnhub_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def check_finnhub_key(self) -> Self:
        """Refuse to load with Finnhub but no key, instead of failing on the
        first price request."""
        key = self.finnhub_api_key
        if self.market_provider == "finnhub" and not (
            key and key.get_secret_value()
        ):
            raise ValueError("MARKET_PROVIDER=finnhub needs FINNHUB_API_KEY")
        return self


@lru_cache
def get_provider_settings() -> ProviderSettings:
    """Return the provider settings, read once per process."""
    return ProviderSettings()
