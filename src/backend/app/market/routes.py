"""Market's HTTP routes: the asset list with prices, and provider usage."""

from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock, get_clock
from app.core.db import get_db
from app.core.money import Money
from app.market.calendar import NEW_YORK
from app.market.models import Asset, ProviderRequest
from app.market.providers import provider_type
from app.market.providers.settings import (
    ProviderSettings,
    get_provider_settings,
)
from app.market.queries import get_current_price, is_market_open

router = APIRouter(tags=["market"])


class AssetPrice(BaseModel):
    symbol: str
    name: str
    # The price fields are null until the asset's first price arrives.
    price: Money | None
    price_currency: str
    quoted_at: datetime | None
    obtained_at: datetime | None
    delayed: bool


class AssetList(BaseModel):
    market_open: bool
    assets: list[AssetPrice]


class Usage(BaseModel):
    calls_last_minute: int
    busiest_minute_today: int
    calls_today: int
    # The chosen provider's limit, or None if it has none, such as the fake.
    limit_per_minute: int | None


@router.get("/assets")
def list_assets(
    db: Session = Depends(get_db), clock: Clock = Depends(get_clock)
) -> AssetList:
    """Every tradable asset with its newest price (FR_MktRealPrices)."""
    now = clock()
    assets = db.scalars(
        select(Asset).where(Asset.is_tradable).order_by(Asset.symbol)
    )
    listed = []
    for asset in assets:
        current = get_current_price(db, asset.asset_id, now)
        listed.append(
            AssetPrice(
                symbol=asset.symbol,
                name=asset.name,
                price=current.price if current else None,
                price_currency=asset.price_currency,
                quoted_at=current.quoted_at if current else None,
                obtained_at=current.obtained_at if current else None,
                delayed=current.delayed if current else False,
            )
        )
    return AssetList(market_open=is_market_open(now), assets=listed)


@router.get("/market/usage")
def provider_usage(
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: ProviderSettings = Depends(get_provider_settings),
) -> Usage:
    """How many calls the server made to the market data provider, to check
    it stays under the chosen provider's limit (SC_MarketData)."""
    now = clock()
    # "Today" is the New York calendar day, the market's day.
    start_of_day = datetime.combine(
        now.astimezone(NEW_YORK).date(), time(), tzinfo=NEW_YORK
    )
    today = ProviderRequest.requested_at.between(start_of_day, now)

    last_minute = db.scalar(
        select(func.count()).where(
            ProviderRequest.requested_at.between(
                now - timedelta(minutes=1), now
            )
        )
    )
    per_minute = (
        select(func.count().label("calls"))
        .where(today)
        .group_by(func.date_trunc("minute", ProviderRequest.requested_at))
        .subquery()
    )
    busiest = db.scalar(select(func.max(per_minute.c.calls)))
    calls_today = db.scalar(select(func.count()).where(today))
    return Usage(
        calls_last_minute=last_minute or 0,
        busiest_minute_today=busiest or 0,
        calls_today=calls_today or 0,
        limit_per_minute=provider_type(settings).calls_per_minute,
    )
