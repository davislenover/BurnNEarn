"""Keeps prices up to date by asking the market data provider for them.

- poll_once asks for every tradable asset's quote once and saves it.
- run_poller calls poll_once every minute while the market is open, on its
  own thread.
- lifespan starts that thread when the app starts and stops it when the app
  stops, if MARKET_POLLER_ENABLED is on.

They only know the provider through MarketDataProvider, so they work the
same with Finnhub or the fake provider.
"""

import asyncio
import logging
import threading
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractContextManager, asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.clock import Clock, system_clock
from app.core.db import SessionLocal
from app.market.calendar import is_market_open
from app.market.models import Asset, Price, ProviderRequest, RequestOutcome
from app.market.providers import build_provider
from app.market.providers.base import (
    MarketDataError,
    MarketDataProvider,
    Quote,
    RateLimitedError,
    UnknownSymbolError,
)
from app.market.providers.settings import get_provider_settings
from app.market.settings import check_always_open, get_market_settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=60)
# Finnhub's last quote of the day, the official close, can arrive a few
# minutes after the market closes, so keep polling for this long after.
POLL_AFTER_CLOSE = timedelta(minutes=15)
# How long to wait for the thread to finish when the app stops.
STOP_TIMEOUT = timedelta(seconds=15)


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


def should_poll(now: datetime) -> bool:
    """Whether to poll at now: while the market is open, and for
    POLL_AFTER_CLOSE after it closes."""
    return is_market_open(now) or is_market_open(now - POLL_AFTER_CLOSE)


def run_poller(
    stop: threading.Event,
    provider: MarketDataProvider,
    clock: Clock = system_clock,
    session_factory: Callable[[], AbstractContextManager[Session]] = (
        SessionLocal
    ),
    interval: timedelta = POLL_INTERVAL,
) -> None:
    """Poll every interval until stop is set. Runs on its own thread.

    Each poll gets its own session and commits once, like a route does for
    a request. An error is logged and the next poll tries again, so one bad
    minute never stops the thread. With stop already set, it polls once and
    returns, which is how the tests run it.
    """
    while True:
        now = clock()
        if should_poll(now):
            try:
                with session_factory() as session:
                    poll_once(session, provider, now)
                    session.commit()
            except Exception:
                logger.exception("The price poll failed")
        if stop.wait(interval.total_seconds()):
            return


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start the poller thread with the app, and stop it with the app."""
    # Read the settings now, so bad ones stop the app from starting.
    settings = get_market_settings()
    providers = get_provider_settings()
    check_always_open(settings, providers)
    if not settings.market_poller_enabled:
        yield
        return

    stop = threading.Event()
    thread = threading.Thread(
        target=run_poller,
        args=(stop, build_provider(providers)),
        name="market-poller",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop.set()
        await asyncio.to_thread(thread.join, STOP_TIMEOUT.total_seconds())
