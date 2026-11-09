"""What market hands to other modules.

These are read-only copies, never database rows, so another module can't
change market's tables by accident.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.errors import DomainError


@dataclass(frozen=True)
class AssetInfo:
    """One asset, such as a stock."""

    asset_id: uuid.UUID
    symbol: str
    name: str
    # False once an asset is removed from the live market.
    is_tradable: bool


@dataclass(frozen=True)
class CurrentPrice:
    """An asset's newest price, and whether it is out of date."""

    price: Decimal
    # When the provider set this price.
    quoted_at: datetime
    # When the server got it from the provider.
    obtained_at: datetime
    # True when the market is open and the price is older than
    # QUOTE_STALENESS_LIMIT (FR_MktPriceAge).
    delayed: bool


class UnknownAssetError(DomainError):
    code = "unknown_asset"
    message = "There is no asset with that symbol."
    status = 404
