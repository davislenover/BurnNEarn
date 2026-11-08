"""What wallet hands to other modules.

These are read-only copies, never database rows, so another module can't
change a balance by accident.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.core.errors import DomainError


class BalanceChangeReason(StrEnum):
    """Why a balance changed. Each change is stored with one (SEC-22)."""

    ACTIVITY_REWARD = "activity_reward"
    TRADE_PURCHASE = "trade_purchase"


@dataclass(frozen=True)
class LockedPortfolio:
    """What lock_live_portfolio returns, and change_balance asks for.

    Make one only with lock_live_portfolio, and use it only before the
    commit that ends the lock. Nothing checks this, but asking for one makes
    skipping the lock hard to do by accident. Even then, change_balance
    keeps the balance at 0 or more.
    """

    portfolio_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class BalanceChangeReceipt:
    """What change_balance hands back: a copy of the change it recorded."""

    balance_change_id: uuid.UUID
    # Positive for currency added, negative for currency spent.
    amount: Decimal
    # The balance right after this change.
    cash_balance_after: Decimal


class InsufficientFundsError(DomainError):
    code = "insufficient_funds"
    message = "You don't have enough currency for this."
    status = 409
