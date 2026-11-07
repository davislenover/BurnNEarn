"""The wallet module's tables: portfolios and their balance changes."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.wallet.types import BalanceChangeReason

# Up to 12 digits before the decimal point and 4 after.
AMOUNT = Numeric(16, 4)

_REASONS = ", ".join(f"'{reason}'" for reason in BalanceChangeReason)


class Portfolio(Base):
    """A user's currency and, later, what they own. The live portfolio is
    the one with no scenario. Market scenarios add others later."""

    __tablename__ = "portfolios"
    __table_args__ = (
        # A balance can never go below 0 (SEC-5). change_balance relies on
        # this as its last line of defence.
        CheckConstraint("cash_balance >= 0", name="cash_balance_not_negative"),
        # Each user has one live portfolio.
        Index(
            "uq_portfolios_live_user_id",
            "user_id",
            unique=True,
            postgresql_where=text("scenario_id IS NULL"),
        ),
    )

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # A string, so wallet never imports another module's models.py.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"))
    cash_balance: Mapped[Decimal] = mapped_column(AMOUNT, server_default="0")
    # Empty for the live portfolio. Market scenarios fill it in later.
    scenario_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BalanceChange(Base):
    """One change to a portfolio's balance, never edited (SEC-22). The
    balance always equals the sum of its portfolio's changes."""

    __tablename__ = "balance_changes"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_not_zero"),
        CheckConstraint(f"reason IN ({_REASONS})", name="reason_valid"),
        # An activity reward is for one day of activity. Nothing else is.
        CheckConstraint(
            "(reason = 'activity_reward') = (activity_date IS NOT NULL)",
            name="activity_date_only_for_rewards",
        ),
    )

    balance_change_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    # Deleted with its portfolio, so resetting the demo leaves nothing
    # behind. Indexed, since that delete and every sum look rows up by it.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.portfolio_id", ondelete="CASCADE"), index=True
    )
    # Positive to add, negative to spend.
    amount: Mapped[Decimal] = mapped_column(AMOUNT)
    reason: Mapped[str] = mapped_column(String(16))
    # The day of activity a reward pays for, in the user's time zone.
    activity_date: Mapped[date | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
