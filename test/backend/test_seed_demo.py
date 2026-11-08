"""Tests for the demo seed script, app/scripts/seed_demo.py."""

import uuid
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.scripts.seed_demo import reset, seed
from app.users.interface import create_user
from app.users.models import User
from app.users.types import DEMO_USER_ID, CurrentUser
from app.wallet.models import BalanceChange, Portfolio
from app.wallet.queries import get_balance, live_portfolio_id


def count(session: Session, statement: Select) -> int:
    return session.scalar(
        select(func.count()).select_from(statement.subquery())
    )


def demo_users(session: Session) -> int:
    return count(session, select(User).where(User.user_id == DEMO_USER_ID))


def demo_portfolios(session: Session) -> int:
    return count(
        session, select(Portfolio).where(Portfolio.user_id == DEMO_USER_ID)
    )


def changes_of(session: Session, portfolio_id: uuid.UUID) -> int:
    return count(
        session,
        select(BalanceChange).where(
            BalanceChange.portfolio_id == portfolio_id
        ),
    )


def test_seed_adds_the_demo_user_with_a_portfolio_at_0(
    db_session: Session,
) -> None:
    portfolio_id = seed(db_session)

    assert demo_users(db_session) == 1
    assert live_portfolio_id(db_session, DEMO_USER_ID) == portfolio_id
    assert get_balance(db_session, portfolio_id) == 0


def test_running_seed_twice_does_not_make_a_second_demo_user(
    db_session: Session,
) -> None:
    first = seed(db_session)
    second = seed(db_session)

    assert second == first
    assert demo_users(db_session) == 1
    assert demo_portfolios(db_session) == 1


def test_seed_adds_a_portfolio_when_the_demo_user_has_none(
    db_session: Session,
) -> None:
    create_user(db_session, DEMO_USER_ID)

    portfolio_id = seed(db_session)

    assert demo_users(db_session) == 1
    assert live_portfolio_id(db_session, DEMO_USER_ID) == portfolio_id


def test_reset_leaves_the_demo_portfolio_at_0_with_no_balance_changes(
    db_session: Session, make_portfolio
) -> None:
    old = make_portfolio(
        Decimal("500"), user=CurrentUser(user_id=DEMO_USER_ID)
    )

    new_portfolio_id = reset(db_session)

    assert get_balance(db_session, new_portfolio_id) == 0
    assert changes_of(db_session, new_portfolio_id) == 0
    # The old portfolio's changes went with it.
    assert changes_of(db_session, old.portfolio_id) == 0
    assert demo_users(db_session) == 1
    assert demo_portfolios(db_session) == 1


def test_reset_works_before_the_demo_user_exists(
    db_session: Session,
) -> None:
    portfolio_id = reset(db_session)

    assert get_balance(db_session, portfolio_id) == 0
    assert demo_users(db_session) == 1