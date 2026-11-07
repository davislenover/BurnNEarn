"""Keeps prices up to date by asking the market data provider for them.

- poll_once asks for every tradable asset's quote once and saves it.
- run_poller calls poll_once every minute while the market is open, on its
  own thread.
- lifespan starts that thread when the app starts and stops it when the app
  stops, if MARKET_POLLER_ENABLED is on.
- health tells GET /v1/health whether the thread is running and whether its
  latest poll worked.

They only know the provider through MarketDataProvider, so they work the
same with Finnhub or the fake provider.
"""

import asyncio
import logging
import threading
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.clock import Clock, system_clock
from app.core.db import SessionLocal
from app.core.plugins import ModuleHealth
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


@dataclass
class _Status:
    """What health reports. lifespan and run_poller write it, and the
    health route reads it."""

    # The poller thread while the app runs, or None while the poller is off.
    thread: threading.Thread | None = None
    # Whether the latest poll failed. See run_poller.
    last_poll_failed: bool = False


_status = _Status()


def poll_once(
    session: Session, provider: MarketDataProvider, now: datetime
) -> bool:
    """Ask the provider for each tradable asset's quote and save it.

    A provider error or a refused save for one asset doesn't stop the
    others. Hitting the provider's request limit stops this poll, and the
    next poll starts again. Every call is recorded in provider_requests.
    Everything is flushed, so the same session sees it, but nothing is
    committed: the caller does that.

    Returns True only if it saved a quote for every tradable asset. So a
    provider that is down, or a wrong key, shows up as a failed poll even
    though no error reaches the caller.
    """
    assets = session.execute(
        select(Asset.asset_id, Asset.symbol)
        .where(Asset.is_tradable)
        .order_by(Asset.symbol)
    ).all()

    saved_all = True
    for asset_id, symbol in assets:
        try:
            quote = provider.get_quote(symbol)
        except RateLimitedError:
            _record(session, symbol, now, RequestOutcome.RATE_LIMITED)
            logger.warning("Request limit reached at %s, stopping", symbol)
            saved_all = False
            break
        except UnknownSymbolError:
            _record(session, symbol, now, RequestOutcome.UNKNOWN_SYMBOL)
            logger.warning("The provider has no price for %s", symbol)
            saved_all = False
            continue
        except MarketDataError as error:
            _record(session, symbol, now, RequestOutcome.ERROR)
            logger.warning("No price for %s: %s", symbol, error)
            saved_all = False
            continue

        _record(session, symbol, now, RequestOutcome.OK)
        try:
            # A savepoint, so a bad quote undoes only itself.
            with session.begin_nested():
                save_quote(session, asset_id, quote)
        except SQLAlchemyError:
            logger.exception("Could not save the price for %s", symbol)
            saved_all = False

    session.flush()
    return saved_all


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
    minute never stops the thread. A poll fails if it raises an error or
    misses any asset's price, and health shows that until the next poll.
    With stop already set, it runs at most one poll and returns, which is
    how the tests run it.
    """
    while True:
        now = clock()
        if should_poll(now):
            try:
                with session_factory() as session:
                    saved_all = poll_once(session, provider, now)
                    session.commit()
                _status.last_poll_failed = not saved_all
            except Exception:
                logger.exception("The price poll failed")
                _status.last_poll_failed = True
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
    _status.last_poll_failed = False
    thread.start()
    _status.thread = thread
    try:
        yield
    finally:
        stop.set()
        await asyncio.to_thread(thread.join, STOP_TIMEOUT.total_seconds())
        # The app is stopping, so the poller is off rather than stopped.
        # _status assumes one app with the poller on per process, as the MIS
        # does. The check keeps one test's app from clearing another's.
        if _status.thread is thread:
            _status.thread = None


def health() -> ModuleHealth:
    """How the price poller is doing, for GET /v1/health."""
    thread = _status.thread
    if thread is None:
        return ModuleHealth(status="ok", detail="poller off")
    if not thread.is_alive():
        # The thread ended while the app still runs.
        return ModuleHealth(status="degraded", detail="poller stopped")
    if _status.last_poll_failed:
        # This shows until the next poll, which may be the next trading day.
        return ModuleHealth(status="degraded", detail="last poll failed")
    return ModuleHealth(status="ok")
