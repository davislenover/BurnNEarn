"""Tests for the prices table created by migration 0003."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Connection, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.db import engine
from app.models import Asset, Price

QUOTED_AT = datetime(2026, 10, 26, 18, 42, 19, tzinfo=UTC)


def aapl_id(connection: Connection) -> uuid.UUID:
    return connection.execute(
        select(Asset.asset_id).where(Asset.symbol == "AAPL")
    ).scalar_one()


def test_price_is_stored_exactly_with_currency_and_both_times(
    database: None,
) -> None:
    with engine.connect() as connection:
        before = connection.execute(
            select(func.clock_timestamp())
        ).scalar_one()
        row = connection.execute(
            insert(Price)
            .values(
                asset_id=aapl_id(connection),
                price=Decimal("342.88"),
                quoted_at=QUOTED_AT,
            )
            .returning(
                Price.price,
                Price.price_currency,
                Price.quoted_at,
                Price.obtained_at,
            )
        ).one()
        after = connection.execute(select(func.clock_timestamp())).scalar_one()
        connection.rollback()

    assert row.price == Decimal("342.88")
    assert row.price_currency == "USD"
    assert row.quoted_at == QUOTED_AT
    # Set by the database when the row is added, not when the transaction
    # started.
    assert before <= row.obtained_at <= after


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"price_currency": "CAD"}, "only USD prices (SEC-27)"),
        ({"price": Decimal(0)}, "no zero prices"),
        ({"price": Decimal("-1")}, "no negative prices"),
        ({"asset_id": uuid.uuid4()}, "only prices of known assets"),
        ({"quoted_at": None}, "every price has its quote time"),
    ],
)
def test_prices_table_rejects_invalid_rows(
    database: None, changes: dict[str, object], reason: str
) -> None:
    with engine.connect() as connection:
        values = {
            "asset_id": aapl_id(connection),
            "price": Decimal("342.88"),
            "quoted_at": QUOTED_AT,
        } | changes
        with pytest.raises(IntegrityError):
            connection.execute(insert(Price).values(**values))
        connection.rollback()


def test_same_quote_is_stored_once(database: None) -> None:
    with engine.connect() as connection:
        values = {
            "asset_id": aapl_id(connection),
            "price": Decimal("342.88"),
            "quoted_at": QUOTED_AT,
        }
        connection.execute(insert(Price).values(**values))
        # A later quote of the same asset is a new row.
        connection.execute(
            insert(Price).values(
                values | {"quoted_at": QUOTED_AT + timedelta(minutes=1)}
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(insert(Price).values(**values))
        connection.rollback()
