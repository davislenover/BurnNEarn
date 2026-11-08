"""The trading module's tables: trades, and the shares each portfolio holds.

Foreign keys are written as strings, such as "assets.asset_id", so trading
never imports another module's models.py (rule 1).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# The same types as prices.price and wallet's amounts.
PRICE = Numeric(12, 4)
AMOUNT = Numeric(16, 4)


class Trade(Base):
    """One buy, never edited. A repeat of its request gets this row back."""

    __tablename__ = "trades"
    __table_args__ = (
        # One trade per request_id in a portfolio, so a retry never buys
        # twice (FR_MktNoDuplicate).
        UniqueConstraint("portfolio_id", "request_id"),
        CheckConstraint("trade_type = 'buy'", name="trade_type_valid"),
        CheckConstraint("status = 'executed'", name="status_valid"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        # PostgreSQL counts NaN as above every number, so it is refused by
        # name.
        CheckConstraint(
            "unit_price > 0 AND unit_price <> 'NaN'",
            name="unit_price_positive",
        ),
        # The cost is exactly the quantity times the price, never rounded.
        CheckConstraint(
            "currency_amount = quantity * unit_price", name="amount_matches"
        ),
        CheckConstraint(
            "cash_balance_after >= 0 AND cash_balance_after <> 'NaN'",
            name="cash_balance_after_not_negative",
        ),
    )

    trade_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # The phone's ID for this buy. A retry sends the same one.
    request_id: Mapped[uuid.UUID]
    # Deleted with its portfolio, so resetting the demo leaves nothing.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.portfolio_id", ondelete="CASCADE")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.asset_id"))
    # Plain strings until selling and queued orders add a second value.
    trade_type: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int]
    # The price paid for each share.
    unit_price: Mapped[Decimal] = mapped_column(PRICE)
    # What the trade cost.
    currency_amount: Mapped[Decimal] = mapped_column(AMOUNT)
    # The balance right after paying, so a repeat gets the same reply.
    cash_balance_after: Mapped[Decimal] = mapped_column(AMOUNT)
    status: Mapped[str] = mapped_column(String(8))
    # The wallet change that paid for this trade. One payment pays for one
    # trade.
    balance_change_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("balance_changes.balance_change_id"), unique=True
    )
    # Set by buy from the clock, not by the database, so the reply and the
    # row agree.
    created_at: Mapped[datetime]


class Holding(Base):
    """How many shares of one stock a portfolio holds."""

    __tablename__ = "holdings"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_not_negative"),
    )

    # The key is both columns, so a portfolio has one row per stock.
    # Deleted with its portfolio, like trades.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.portfolio_id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.asset_id"), primary_key=True
    )
    quantity: Mapped[int]
