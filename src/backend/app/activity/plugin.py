"""Adds activity to the app. Only app/registry.py imports this."""

from app.activity import (
    models,  # noqa: F401  (registers the table)
    routes,
)
from app.core.plugins import Plugin

PLUGIN = Plugin(name="activity", router=routes.router)
