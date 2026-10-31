"""Market data from Finnhub (https://finnhub.io/docs/api/quote)."""

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx2
from pydantic import SecretStr

from app.market.provider import (
    MarketDataError,
    Quote,
    RateLimitedError,
    UnknownSymbolError,
)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubProvider:
    """Gets quotes from Finnhub. Only the asset's symbol is sent (HA SEC-11).

    The API key goes in a request header rather than the URL, so it never
    appears in logged URLs or error messages (HA SEC-33).
    """

    def __init__(
        self, api_key: SecretStr, client: httpx2.Client | None = None
    ) -> None:
        self._api_key = api_key
        self._client = client or httpx2.Client(
            base_url=FINNHUB_BASE_URL, timeout=10.0
        )

    def get_quote(self, symbol: str) -> Quote:
        try:
            response = self._client.get(
                "/quote",
                params={"symbol": symbol},
                headers={"X-Finnhub-Token": self._api_key.get_secret_value()},
            )
        except httpx2.TransportError as error:
            raise MarketDataError(
                f"Could not reach Finnhub: {error}"
            ) from error

        if response.status_code == 429:
            raise RateLimitedError("Finnhub request limit reached")
        if response.status_code != 200:
            raise MarketDataError(
                f"Finnhub returned HTTP {response.status_code} for {symbol}"
            )

        try:
            # Read numbers as Decimal so prices are exact, not floats.
            data = json.loads(response.text, parse_float=Decimal)
            price = Decimal(data["c"])
            quoted_at = datetime.fromtimestamp(int(data["t"]), tz=UTC)
        except (ValueError, KeyError, TypeError, InvalidOperation) as error:
            raise MarketDataError(
                f"Unexpected Finnhub response for {symbol}"
            ) from error

        # Finnhub answers an unknown symbol with zeros instead of an error.
        if price <= 0 or quoted_at.timestamp() == 0:
            raise UnknownSymbolError(f"Finnhub has no price for {symbol}")

        return Quote(symbol=symbol, price=price, quoted_at=quoted_at)

    def close(self) -> None:
        self._client.close()
