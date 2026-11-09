"""Tests for what other modules may read from market."""

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.market.models import Asset, Price
from app.market.queries import (
    get_asset,
    get_asset_by_symbol,
    get_current_price,
)
from app.market.types import UnknownAssetError

# Tuesday Nov 10, 2026 at 10:00 in New York: the market is open.
OPEN = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
# Saturday Nov 14, 2026 at 10:00 in New York: the market is closed.
CLOSED = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)


def add_price(
    session: Session, asset_id: uuid.UUID, price: str, quoted_at: datetime
) -> None:
    session.add(
        Price(asset_id=asset_id, price=Decimal(price), quoted_at=quoted_at)
    )
    session.flush()


def test_an_asset_is_found_by_its_symbol_as_a_read_only_copy(
    db_session: Session,
) -> None:
    asset = get_asset_by_symbol(db_session, "AAPL")

    assert asset.symbol == "AAPL"
    assert asset.is_tradable
    assert get_asset(db_session, asset.asset_id) == asset
    with pytest.raises(dataclasses.FrozenInstanceError):
        asset.is_tradable = False  # type: ignore[misc]


def test_a_removed_asset_is_still_found_but_not_tradable(
    db_session: Session,
) -> None:
    db_session.execute(
        update(Asset).where(Asset.symbol == "AAPL").values(is_tradable=False)
    )

    assert get_asset_by_symbol(db_session, "AAPL").is_tradable is False


def test_an_unknown_symbol_or_id_is_refused_with_404(
    db_session: Session,
) -> None:
    with pytest.raises(UnknownAssetError) as error:
        get_asset_by_symbol(db_session, "NOPE")
    assert error.value.status == 404
    assert error.value.code == "unknown_asset"

    with pytest.raises(UnknownAssetError):
        get_asset(db_session, uuid.uuid4())


def test_the_newest_quote_is_the_current_price(db_session: Session) -> None:
    asset = get_asset_by_symbol(db_session, "AAPL")
    add_price(db_session, asset.asset_id, "101", OPEN - timedelta(minutes=1))
    add_price(db_session, asset.asset_id, "100", OPEN - timedelta(minutes=2))

    current = get_current_price(db_session, asset.asset_id, OPEN)

    assert current is not None
    assert current.price == Decimal("101")
    assert current.quoted_at == OPEN - timedelta(minutes=1)


@pytest.mark.parametrize(
    ("now", "age", "delayed"),
    [
        (OPEN, timedelta(minutes=15), False),
        (OPEN, timedelta(minutes=16), True),
        # While the market is closed, an old price is expected.
        (CLOSED, timedelta(days=1), False),
    ],
)
def test_a_price_is_delayed_only_when_old_while_the_market_is_open(
    db_session: Session, now: datetime, age: timedelta, delayed: bool
) -> None:
    asset = get_asset_by_symbol(db_session, "AAPL")
    add_price(db_session, asset.asset_id, "100", now - age)

    current = get_current_price(db_session, asset.asset_id, now)

    assert current is not None
    assert current.delayed is delayed
