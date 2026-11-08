"""Adds the market module to the app. Only app/registry.py imports this."""

from app.core.plugins import Plugin
from app.market import (
    models,  # noqa: F401  (registers the tables)
    poller,
    routes,
)

PLUGIN = Plugin(
    name="market",
    router=routes.router,
    lifespan=poller.lifespan,
    health=poller.health,
)
