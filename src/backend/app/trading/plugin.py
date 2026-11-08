"""Adds the trading module to the app. Only app/registry.py imports this."""

from app.core.plugins import Plugin
from app.trading import models  # noqa: F401  (registers the tables)

# No routes yet. POST /v1/me/trades and GET /v1/me/portfolio come later.
PLUGIN = Plugin(name="trading")
