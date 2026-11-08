"""Tests for the wallet's money code: the lock, change_balance and queries."""

import dataclasses
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.users.interface import create_user
from app.users.models import User
from app.wallet.interface import (
    change_balance,
    create_live_portfolio,
    delete_portfolio,
    lock_live_portfolio,
)
from app.wallet.models import BalanceChange, Portfolio
from app.wallet.queries import activity_paid, get_balance, live_portfolio_id
from app.wallet.types import (
    BalanceChangeReason,
    InsufficientFundsError,
    LockedPortfolio,
)

REWARD = BalanceChangeReason.ACTIVITY_REWARD
PURCHASE = BalanceChangeReason.TRADE_PURCHASE
DAY = date(2026, 11, 7)


@pytest.fixture
def session(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """db_session, but a commit fails the test. The wallet never commits:
    the route that calls it commits once, so a buy is all or nothing."""

    def no_commit() -> None:
        raise AssertionError("wallet code must never commit")

    monkeypatch.setattr(db_session, "commit", no_commit)
    return db_session


def new_wallet(session: Session) -> LockedPortfolio:
    """A new user with a live portfolio at 0, locked."""
    user_id = create_user(session)
    create_live_portfolio(session, user_id)
    return lock_live_portfolio(session, user_id)


def changes(session: Session, portfolio_id: uuid.UUID) -> list[Decimal]:
    return list(
        session.scalars(
            select(BalanceChange.amount).where(
                BalanceChange.portfolio_id == portfolio_id
            )
        )
    )


def test_a_live_portfolio_starts_at_zero(session: Session) -> None:
    user_id = create_user(session)

    portfolio_id = create_live_portfolio(session, user_id)

    assert live_portfolio_id(session, user_id) == portfolio_id
    assert get_balance(session, portfolio_id) == Decimal("0")


def test_the_live_portfolio_is_found_and_locked_not_a_scenario_one(
    session: Session,
) -> None:
    user_id = create_user(session)
    live_id = create_live_portfolio(session, user_id)
    session.add(Portfolio(user_id=user_id, scenario_id=uuid.uuid4()))
    session.flush()

    assert live_portfolio_id(session, user_id) == live_id
    assert lock_live_portfolio(session, user_id).portfolio_id == live_id


def test_adding_and_spending_change_the_balance_exactly(
    session: Session,
) -> None:
    locked = new_wallet(session)

    added = change_balance(session, locked, Decimal("500"), REWARD, DAY)
    spent = change_balance(session, locked, Decimal("-101.5"), PURCHASE)

    assert added.cash_balance_after == Decimal("500")
    assert spent.amount == Decimal("-101.5")
    assert spent.cash_balance_after == Decimal("398.5")
    assert get_balance(session, locked.portfolio_id) == Decimal("398.5")
    # Each change is recorded once, with its reason.
    reason = session.scalar(
        select(BalanceChange.reason).where(
            BalanceChange.balance_change_id == spent.balance_change_id
        )
    )
    assert reason == PURCHASE


def test_a_portfolio_already_loaded_shows_the_new_balance(
    session: Session,
) -> None:
    locked = new_wallet(session)
    loaded = session.get(Portfolio, locked.portfolio_id)
    assert loaded is not None

    change_balance(session, locked, Decimal("7.5"), REWARD, DAY)

    assert loaded.cash_balance == Decimal("7.5")


def test_spending_the_whole_balance_leaves_zero(session: Session) -> None:
    locked = new_wallet(session)
    change_balance(session, locked, Decimal("100"), REWARD, DAY)

    receipt = change_balance(session, locked, Decimal("-100"), PURCHASE)

    assert receipt.cash_balance_after == Decimal("0")


@pytest.mark.parametrize(
    "amount",
    [
        Decimal("-100.0001"),
        # Far more than any balance can hold, such as a buy of 10^23 shares.
        Decimal(10**23) * Decimal("-101.5"),
    ],
)
def test_spending_more_than_the_balance_is_refused_and_changes_nothing(
    session: Session, amount: Decimal
) -> None:
    locked = new_wallet(session)
    change_balance(session, locked, Decimal("100"), REWARD, DAY)

    with pytest.raises(InsufficientFundsError):
        change_balance(session, locked, amount, PURCHASE)

    assert get_balance(session, locked.portfolio_id) == Decimal("100")
    assert changes(session, locked.portfolio_id) == [Decimal("100")]


def test_the_balance_is_always_the_sum_of_its_changes(
    session: Session,
) -> None:
    locked = new_wallet(session)
    amounts = ["300", "-12.3456", "0.0001", "-287.6545", "42"]
    for amount in amounts:
        reason = REWARD if not amount.startswith("-") else PURCHASE
        day = DAY if reason == REWARD else None
        change_balance(session, locked, Decimal(amount), reason, day)

    total = session.scalar(
        select(func.sum(BalanceChange.amount)).where(
            BalanceChange.portfolio_id == locked.portfolio_id
        )
    )
    assert get_balance(session, locked.portfolio_id) == total
    assert total == sum(Decimal(a) for a in amounts)


@pytest.mark.parametrize(
    ("amount", "reason", "day"),
    [
        (Decimal("0"), REWARD, DAY),
        # The database would round these quietly to 4 decimals.
        (Decimal("1.00001"), REWARD, DAY),
        (Decimal("-1.00001"), PURCHASE, None),
        (Decimal("NaN"), REWARD, DAY),
        (Decimal("Infinity"), REWARD, DAY),
        (100, REWARD, DAY),
        # A reward adds currency and a purchase spends it.
        (Decimal("1"), PURCHASE, None),
        (Decimal("-1"), REWARD, DAY),
        # A reward is for one day of activity. Nothing else has a day.
        (Decimal("1"), REWARD, None),
        (Decimal("-1"), PURCHASE, DAY),
        # A datetime would be stored as whatever day it is in UTC.
        (Decimal("1"), REWARD, datetime(2026, 11, 7, 23, 30, tzinfo=UTC)),
    ],
)
def test_a_change_that_makes_no_sense_is_refused_before_anything_changes(
    session: Session, amount: object, reason: str, day: date | None
) -> None:
    locked = new_wallet(session)
    change_balance(session, locked, Decimal("50"), REWARD, DAY)

    with pytest.raises(ValueError):
        change_balance(session, locked, amount, reason, day)

    assert get_balance(session, locked.portfolio_id) == Decimal("50")
    assert changes(session, locked.portfolio_id) == [Decimal("50")]


def test_activity_paid_sums_only_that_days_rewards(session: Session) -> None:
    locked = new_wallet(session)
    other = new_wallet(session)
    change_balance(session, locked, Decimal("10"), REWARD, DAY)
    change_balance(session, locked, Decimal("2.5"), REWARD, DAY)
    change_balance(session, locked, Decimal("7"), REWARD, date(2026, 11, 6))
    change_balance(session, locked, Decimal("-5"), PURCHASE)
    change_balance(session, other, Decimal("99"), REWARD, DAY)

    assert activity_paid(session, locked.portfolio_id, DAY) == Decimal("12.5")
    assert activity_paid(
        session, locked.portfolio_id, date(2026, 11, 5)
    ) == Decimal("0")
    with pytest.raises(ValueError):
        activity_paid(
            session, locked.portfolio_id, datetime(2026, 11, 7, tzinfo=UTC)
        )


def test_delete_portfolio_removes_only_that_portfolio_and_its_changes(
    session: Session,
) -> None:
    locked = new_wallet(session)
    other = new_wallet(session)
    change_balance(session, locked, Decimal("10"), REWARD, DAY)
    change_balance(session, other, Decimal("10"), REWARD, DAY)

    delete_portfolio(session, locked.portfolio_id)

    assert session.get(Portfolio, locked.portfolio_id) is None
    assert changes(session, locked.portfolio_id) == []
    assert get_balance(session, other.portfolio_id) == Decimal("10")
    assert changes(session, other.portfolio_id) == [Decimal("10")]


def test_the_phone_sees_insufficient_funds_as_a_409() -> None:
    assert InsufficientFundsError.code == "insufficient_funds"
    assert InsufficientFundsError.status == 409


def test_a_receipt_is_read_only(session: Session) -> None:
    locked = new_wallet(session)
    receipt = change_balance(session, locked, Decimal("1"), REWARD, DAY)

    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.cash_balance_after = Decimal("1000")


def test_a_second_transaction_waits_for_the_lock(database: None) -> None:
    # Two real connections, so this commits its own rows and removes them
    # at the end, instead of using db_session.
    with SessionLocal() as setup:
        user_id = create_user(setup)
        create_live_portfolio(setup, user_id)
        setup.commit()

    first, second = SessionLocal(), SessionLocal()
    try:
        lock_live_portfolio(first, user_id)

        # Give up after 200 ms instead of waiting for the first one.
        second.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(OperationalError, match="lock timeout"):
            lock_live_portfolio(second, user_id)
        second.rollback()

        # Once the first transaction ends, the second gets the lock.
        first.rollback()
        second.execute(text("SET LOCAL lock_timeout = '2s'"))
        assert lock_live_portfolio(second, user_id).user_id == user_id
    finally:
        # Both end before the cleanup, so it never waits on the lock.
        first.rollback()
        second.rollback()
        first.close()
        second.close()
        with SessionLocal() as cleanup:
            cleanup.execute(
                delete(Portfolio).where(Portfolio.user_id == user_id)
            )
            cleanup.execute(delete(User).where(User.user_id == user_id))
            cleanup.commit()
