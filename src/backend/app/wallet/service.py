"""The wallet's rules. Other modules reach them through interface.py.

Nothing here commits. The route that calls these commits once, so a change
to a balance and whatever it pays for are saved together or not at all.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.wallet.models import BalanceChange, Portfolio
from app.wallet.types import (
    BalanceChangeReason,
    BalanceChangeReceipt,
    InsufficientFundsError,
    LockedPortfolio,
)

# Amounts are stored with 4 decimals. One with more would be rounded
# quietly by the database, so it is refused instead.
FOUR_DECIMALS = Decimal("0.0001")


def lock_live_portfolio(
    session: Session, user_id: uuid.UUID
) -> LockedPortfolio:
    """Lock the user's live portfolio until this transaction ends.

    Every route that changes money calls this first. Two requests for the
    same portfolio then run one after the other, and the second sees what
    the first saved, instead of both acting on the same old balance.
    """
    portfolio_id = session.execute(
        select(Portfolio.portfolio_id)
        .where(Portfolio.user_id == user_id, Portfolio.scenario_id.is_(None))
        .with_for_update()
    ).scalar_one()
    return LockedPortfolio(portfolio_id=portfolio_id, user_id=user_id)


def change_balance(
    session: Session,
    locked: LockedPortfolio,
    amount: Decimal,
    reason: BalanceChangeReason,
    activity_date: date | None = None,
) -> BalanceChangeReceipt:
    """Add amount to the locked portfolio's balance and record why.

    This is the only code allowed to change cash_balance. One UPDATE adds
    amount only if the balance stays at 0 or more, so the balance can't go
    below 0 even if a caller forgot the lock. If it would, this raises
    InsufficientFundsError and has changed nothing.

    It raises ValueError, before changing anything, unless:
    - amount is a Decimal with at most 4 decimals, and not 0. So skip a
      top-up of 0 instead of calling this
    - a reward adds currency and a purchase spends it
    - a reward has the activity_date (a date, not a datetime) it pays for,
      and nothing else has one
    """
    _check_amount(amount)
    is_reward = reason == BalanceChangeReason.ACTIVITY_REWARD
    if is_reward != (amount > 0):
        raise ValueError("A reward adds currency and a purchase spends it")
    if is_reward != (activity_date is not None):
        raise ValueError(
            "An activity reward needs an activity_date, and nothing else"
            " has one"
        )
    if isinstance(activity_date, datetime):
        raise ValueError("activity_date must be a date, not a datetime")

    # Returning the row refreshes a Portfolio this session already loaded,
    # so it never shows an old balance.
    portfolio = session.execute(
        update(Portfolio)
        .where(
            Portfolio.portfolio_id == locked.portfolio_id,
            Portfolio.cash_balance + amount >= 0,
        )
        .values(cash_balance=Portfolio.cash_balance + amount)
        .returning(Portfolio)
        .execution_options(synchronize_session=False, populate_existing=True)
    ).scalar_one_or_none()
    if portfolio is None:
        raise InsufficientFundsError()
    new_balance = portfolio.cash_balance

    change = BalanceChange(
        portfolio_id=locked.portfolio_id,
        amount=amount,
        reason=reason,
        activity_date=activity_date,
    )
    session.add(change)
    session.flush()
    return BalanceChangeReceipt(
        balance_change_id=change.balance_change_id,
        amount=amount,
        cash_balance_after=new_balance,
    )


def create_live_portfolio(session: Session, user_id: uuid.UUID) -> uuid.UUID:
    """Give a user their live portfolio, starting at 0. Never commits."""
    portfolio = Portfolio(user_id=user_id)
    session.add(portfolio)
    session.flush()
    return portfolio.portfolio_id


def delete_portfolio(session: Session, portfolio_id: uuid.UUID) -> None:
    """Delete a portfolio. Never commits.

    It is one DELETE, so the database also removes the rows under the
    portfolio in the same statement: its balance changes, and other
    modules' rows whose foreign key to it is ON DELETE CASCADE.
    """
    session.execute(
        delete(Portfolio).where(Portfolio.portfolio_id == portfolio_id)
    )


def _check_amount(amount: Decimal) -> None:
    if not isinstance(amount, Decimal) or not amount.is_finite():
        raise ValueError(f"Not an amount of currency: {amount!r}")
    if amount == 0:
        raise ValueError("A balance change can't be 0")
    # Only an amount written with more than 4 decimals needs the quantize.
    # That also keeps quantize away from huge amounts, which it can't do.
    exponent = amount.as_tuple().exponent
    if (
        isinstance(exponent, int)
        and exponent < -4
        and amount != amount.quantize(FOUR_DECIMALS)
    ):
        raise ValueError(f"More than 4 decimals: {amount}")
