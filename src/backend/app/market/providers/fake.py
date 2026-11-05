"""Made-up prices, for development and tests. Needs no Finnhub key."""

import random
import zlib
from decimal import Decimal

from app.core.clock import Clock, system_clock
from app.market.providers.base import Quote

# Each call moves a price by up to this much, either way.
MAX_STEP = Decimal("0.005")


class FakeProvider:
    """Gives each symbol a made-up price that moves a little on every call,
    quoted at the current time."""

    def __init__(self, clock: Clock = system_clock) -> None:
        self._clock = clock
        self._prices: dict[str, Decimal] = {}
        self._random = random.Random()

    def get_quote(self, symbol: str) -> Quote:
        price = self._prices.get(symbol)
        if price is None:
            # The same start price for a symbol every run, from 20 to 500.
            price = Decimal(20 + zlib.crc32(symbol.encode()) % 481)
        else:
            step = MAX_STEP * Decimal(self._random.uniform(-1, 1))
            price = (price * (1 + step)).quantize(Decimal("0.0001"))
        self._prices[symbol] = price
        return Quote(symbol=symbol, price=price, quoted_at=self._clock())
