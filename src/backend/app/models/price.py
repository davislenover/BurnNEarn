"""Prices obtained from the market data provider (SRS Section 6.3)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import QUOTE_CURRENCY
from app.core.db import Base


class Price(Base):
    """One price for one asset. The rows for an asset are its price history,
    and the one with the latest quoted_at is its current price
    (FR_MktRealPrices)."""

    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint("price > 0", name="price_positive"),
        # Every price is stored with its currency (SEC-27).
        CheckConstraint(
            f"price_currency = '{QUOTE_CURRENCY}'", name="one_currency"
        ),
        # The provider repeats the same quote while the market is closed, so
        # each quote is stored once. This also indexes the lookup of an
        # asset's latest price.
        UniqueConstraint("asset_id", "quoted_at"),
    )

    # A plain counter instead of a UUID: there are many rows and nothing
    # outside the server refers to one.
    price_id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.asset_id"))
    # Up to 8 digits before the decimal point and 4 after.
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    price_currency: Mapped[str] = mapped_column(
        String(3), server_default=QUOTE_CURRENCY
    )
    # When the provider set this price. A price is delayed when this is older
    # than QUOTE_STALENESS_LIMIT while the market is open (FR_MktPriceAge).
    quoted_at: Mapped[datetime]
    # When the server obtained this price from the provider
    # (price_obtained_at in SRS Section 7.2). statement_timestamp() is the
    # time of the insert. now() would be the start of the transaction,
    # which can be before the price was even fetched.
    obtained_at: Mapped[datetime] = mapped_column(
        server_default=func.statement_timestamp()
    )
