"""Assets that users can trade in the live market (SRS Section 6.3)."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import QUOTE_CURRENCY
from app.core.db import Base


class AssetType(StrEnum):
    STOCK = "stock"
    ETF = "etf"


class Asset(Base):
    """One tradable asset, such as a stock. Its prices are stored
    separately, each with the time it was obtained."""

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('stock', 'etf')", name="asset_type_valid"
        ),
        # Every asset is priced in one currency (FR_MktOneCurrency, SEC-27).
        CheckConstraint(
            f"price_currency = '{QUOTE_CURRENCY}'", name="one_currency"
        ),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # Market symbol sent to the market data provider, e.g. "AAPL" (SEC-11).
    symbol: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[str] = mapped_column(String(5))
    price_currency: Mapped[str] = mapped_column(
        String(3), server_default=QUOTE_CURRENCY
    )
    # False once an administrator removes the asset from the live market.
    # Users who hold it can still see and sell it (FR_MktRemovedHoldings).
    is_tradable: Mapped[bool] = mapped_column(server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
