"""Keeps prices up to date by asking the market data provider for them.

poll_once asks for every tradable asset's quote once and saves it. It only
knows the provider through MarketDataProvider, so it works the same with
Finnhub or the fake provider.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.market.models import Asset, Price, ProviderRequest, RequestOutcome
from app.market.providers.base import (
    MarketDataError,
    MarketDataProvider,
    Quote,
    RateLimitedError,
    UnknownSymbolError,
)

logger = logging.getLogger(__name__)


def poll_once(
    session: Session, provider: MarketDataProvider, now: datetime
) -> None:
    """Ask the provider for each tradable asset's quote and save it.

    One asset failing doesn't stop the others. Hitting the provider's
    request limit stops this poll, and the next poll starts again. Every
    call is recorded in provider_requests. Everything is flushed, so the
    same session sees it, but nothing is committed: the caller does that.
    """
    assets = session.execute(
        select(Asset.asset_id, Asset.symbol)
        .where(Asset.is_tradable)
        .order_by(Asset.symbol)
    ).all()

    for asset_id, symbol in assets:
        try:
            quote = provider.get_quote(symbol)
        except RateLimitedError:
            _record(session, symbol, now, RequestOutcome.RATE_LIMITED)
            logger.warning("Request limit reached at %s, stopping", symbol)
            break
        except UnknownSymbolError:
            _record(session, symbol, now, RequestOutcome.UNKNOWN_SYMBOL)
            logger.warning("The provider has no price for %s", symbol)
            continue
        except MarketDataError as error:
            _record(session, symbol, now, RequestOutcome.ERROR)
            logger.warning("No price for %s: %s", symbol, error)
            continue

        _record(session, symbol, now, RequestOutcome.OK)
        try:
            # A savepoint, so a bad quote undoes only itself.
            with session.begin_nested():
                save_quote(session, asset_id, quote)
        except SQLAlchemyError:
            logger.exception("Could not save the price for %s", symbol)

    session.flush()


def save_quote(session: Session, asset_id: uuid.UUID, quote: Quote) -> None:
    """Save a quote, once.

    A quote is identified by its asset and quote time. The provider repeats
    the same quote while nothing trades, so an exact repeat is skipped. If
    the provider later corrects the price, the stored row is updated.
    """
    new = insert(Price).values(
        asset_id=asset_id, price=quote.price, quoted_at=quote.quoted_at
    )
    session.execute(
        new.on_conflict_do_update(
            index_elements=[Price.asset_id, Price.quoted_at],
            set_={
                "price": new.excluded.price,
                "obtained_at": func.statement_timestamp(),
            },
            where=Price.price != new.excluded.price,
        )
    )


def _record(
    session: Session, symbol: str, now: datetime, outcome: RequestOutcome
) -> None:
    session.add(
        ProviderRequest(requested_at=now, symbol=symbol, outcome=outcome)
    )
