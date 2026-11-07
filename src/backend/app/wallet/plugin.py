"""Adds the wallet module to the app. Only app/registry.py imports this."""

from app.core.plugins import Plugin
from app.wallet import models  # noqa: F401  (registers the tables)

# The balance route comes with the demo user (#189).
PLUGIN = Plugin(name="wallet")
