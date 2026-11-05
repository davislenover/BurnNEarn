"""The shape of a plugin: what a module adds to the app.

Each module fills one in, in its plugin.py, and app/registry.py lists them.
create_app() then adds every module without knowing anything about it.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from fastapi import APIRouter, FastAPI

# Work that starts with the app and stops with it, such as a background
# thread. It is an async context manager: code before its yield runs at
# startup, and code after it runs at shutdown.
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


@dataclass(frozen=True)
class Plugin:
    """What one module adds to the app."""

    # The module's folder name, such as "market".
    name: str
    # The module's routes, added under /v1. None if it has no routes yet.
    router: APIRouter | None = None
    # Work that runs while the app runs. None if there is none.
    lifespan: Lifespan | None = None
