"""Adds the wallet module to the app. Only app/registry.py imports this."""

from app.core.plugins import Plugin
from app.wallet import (
    models,  # noqa: F401  (registers the tables)
    routes,
)

PLUGIN = Plugin(name="wallet", router=routes.router)