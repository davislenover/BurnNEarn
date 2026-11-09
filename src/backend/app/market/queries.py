"""What other modules may read from market.

Each function returns a read-only copy from types.py, never a database row.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import QUOTE_STALENESS_LIMIT
from app.market.calendar import is_market_open
from app.market.models import Asset, Price
from app.market.types import AssetInfo, CurrentPrice, UnknownAssetError

__all__ = [
    "get_asset",
    "get_asset_by_symbol",
    "get_current_price",
    "is_delayed",
    "is_market_open",
]


def get_asset_by_symbol(session: Session, symbol: str) -> AssetInfo:
    """The asset with this symbol, such as "AAPL".

    Raises UnknownAssetError (404) if there is none.
    """
    asset = session.scalar(select(Asset).where(Asset.symbol == symbol))
    if asset is None:
        raise UnknownAssetError()
    return _asset_info(asset)


def get_asset(session: Session, asset_id: uuid.UUID) -> AssetInfo:
    """The asset with this id. Raises UnknownAssetError if there is none."""
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise UnknownAssetError()
    return _asset_info(asset)


def get_current_price(
    session: Session, asset_id: uuid.UUID, now: datetime
) -> CurrentPrice | None:
    """The asset's newest price, or None before its first price arrives."""
    price = session.scalar(
        select(Price)
        .where(Price.asset_id == asset_id)
        .order_by(Price.quoted_at.desc())
        .limit(1)
    )
    if price is None:
        return None
    return CurrentPrice(
        price=price.price,
        quoted_at=price.quoted_at,
        obtained_at=price.obtained_at,
        delayed=is_delayed(price.quoted_at, now),
    )


def is_delayed(quoted_at: datetime, now: datetime) -> bool:
    """Whether a price quoted at quoted_at is out of date at now.

    Only while the market is open: once it closes, the last price is
    expected to stay the same until it opens again.
    """
    return is_market_open(now) and now - quoted_at > QUOTE_STALENESS_LIMIT


def _asset_info(asset: Asset) -> AssetInfo:
    return AssetInfo(
        asset_id=asset.asset_id,
        symbol=asset.symbol,
        name=asset.name,
        is_tradable=asset.is_tradable,
    )
