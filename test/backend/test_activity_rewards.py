"""Reward boundaries and top-ups without a database."""

from datetime import date
from decimal import Decimal

import pytest

from app.activity.rewards import allowed_dates, daily_reward, top_up


@pytest.mark.parametrize(
    ("steps", "reward"),
    [
        (0, 0),
        (99, 0),
        (100, 1),
        (8421, 84),
        (40_000, 300),
        (150_000, 300),
        (150_001, 0),
        (200_000, 0),
    ],
)
def test_daily_reward(steps: int, reward: int) -> None:
    assert daily_reward(steps) == Decimal(reward)
    assert isinstance(daily_reward(steps), Decimal)


@pytest.mark.parametrize(
    ("reward", "paid", "owed"),
    [
        ("84", "0", "84"),
        ("85", "84", "1"),
        ("80", "85", "0"),
        ("0", "85", "0"),
        ("85", "85", "0"),
        ("85", "84.5", "0.5"),
    ],
)
def test_only_unpaid_currency_is_owed(
    reward: str, paid: str, owed: str
) -> None:
    assert top_up(Decimal(reward), Decimal(paid)) == Decimal(owed)


def test_allowed_dates_crosses_the_year_without_adding_an_eighth_day() -> None:
    assert allowed_dates(date(2027, 1, 3)) == frozenset(
        {
            date(2027, 1, 3),
            date(2027, 1, 2),
            date(2027, 1, 1),
            date(2026, 12, 31),
            date(2026, 12, 30),
            date(2026, 12, 29),
            date(2026, 12, 28),
        }
    )
