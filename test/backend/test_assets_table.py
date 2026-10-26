"""Tests for the assets table created by migration 0002."""

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.core.db import engine
from app.models import Asset

STARTING_SYMBOLS = {
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "JPM",
    "V",
    "AMD",
}


def test_starting_stocks_are_tradable_usd_stocks(database: None) -> None:
    with engine.connect() as connection:
        rows = connection.execute(
            select(
                Asset.symbol,
                Asset.asset_type,
                Asset.price_currency,
                Asset.is_tradable,
            )
        ).all()

    assert {row.symbol for row in rows} == STARTING_SYMBOLS
    assert all(row.asset_type == "stock" for row in rows)
    assert all(row.price_currency == "USD" for row in rows)
    assert all(row.is_tradable for row in rows)


@pytest.mark.parametrize(
    ("symbol", "asset_type", "price_currency"),
    [
        ("TEST1", "stock", "CAD"),  # only USD prices (FR_MktOneCurrency)
        ("TEST2", "bond", "USD"),  # only stocks and ETFs
        ("AAPL", "stock", "USD"),  # each symbol appears once
    ],
)
def test_assets_table_rejects_invalid_rows(
    database: None, symbol: str, asset_type: str, price_currency: str
) -> None:
    with engine.connect() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(Asset).values(
                    symbol=symbol,
                    name="Test asset",
                    asset_type=asset_type,
                    price_currency=price_currency,
                )
            )
        connection.rollback()
