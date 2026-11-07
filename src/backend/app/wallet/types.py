"""What wallet hands to other modules.

These are read-only copies, never database rows, so another module can't
change a balance by accident.
"""

from enum import StrEnum


class BalanceChangeReason(StrEnum):
    """Why a balance changed. Each change is stored with one (SEC-22)."""

    ACTIVITY_REWARD = "activity_reward"
    TRADE_PURCHASE = "trade_purchase"
