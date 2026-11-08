"""Adds the trading module to the app. Only app/registry.py imports this."""

from app.core.plugins import Plugin
from app.trading import (
    models,  # noqa: F401  (registers the tables)
    routes,
)

PLUGIN = Plugin(name="trading", router=routes.router)
