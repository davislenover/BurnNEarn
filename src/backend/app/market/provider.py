"""What the app needs from a market data provider.

The rest of the backend uses MarketDataProvider instead of a specific
provider, so the provider can change (SC_MarketData) without changing the
code that stores and serves prices.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class Quote:
    """The latest price of one asset, as reported by the provider."""

    symbol: str
    price: Decimal
    # When the provider set this price (not when we fetched it). Used to
    # tell whether a price is out of date (FR_MktPriceAge, HA SEC-2).
    quoted_at: datetime


class MarketDataError(Exception):
    """The provider could not return a usable price."""


class RateLimitedError(MarketDataError):
    """The provider refused the request because of its request limit."""


class UnknownSymbolError(MarketDataError):
    """The provider has no price for this symbol."""


class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote:
        """Return the latest price for symbol, or raise MarketDataError."""
        ...
