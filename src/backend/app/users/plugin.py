"""Adds the users module to the app. Only app/registry.py imports this."""

from app.core.plugins import Plugin
from app.users import models  # noqa: F401  (registers the tables)

# No routes yet. Sign-in brings them later.
PLUGIN = Plugin(name="users")
