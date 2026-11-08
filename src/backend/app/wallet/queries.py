"""What other modules may read from wallet. These never write."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.wallet.models import BalanceChange, Portfolio
from app.wallet.types import BalanceChangeReason

__all__ = ["activity_paid", "get_balance", "live_portfolio_id"]


def live_portfolio_id(session: Session, user_id: uuid.UUID) -> uuid.UUID:
    """The ID of the user's live portfolio."""
    return session.execute(
        select(Portfolio.portfolio_id).where(
            Portfolio.user_id == user_id, Portfolio.scenario_id.is_(None)
        )
    ).scalar_one()


def get_balance(session: Session, portfolio_id: uuid.UUID) -> Decimal:
    """The portfolio's balance, including changes this session made."""
    return session.execute(
        select(Portfolio.cash_balance).where(
            Portfolio.portfolio_id == portfolio_id
        )
    ).scalar_one()


def activity_paid(
    session: Session, portfolio_id: uuid.UUID, activity_date: date
) -> Decimal:
    """How much has been paid in rewards for one day of activity, so a
    step sync only pays the difference (#190)."""
    if isinstance(activity_date, datetime):
        raise ValueError("activity_date must be a date, not a datetime")
    paid = session.execute(
        select(func.coalesce(func.sum(BalanceChange.amount), 0)).where(
            BalanceChange.portfolio_id == portfolio_id,
            BalanceChange.reason == BalanceChangeReason.ACTIVITY_REWARD,
            BalanceChange.activity_date == activity_date,
        )
    ).scalar_one()
    return Decimal(paid)
