"""The shape of a plugin: what a module adds to the app.

Each module fills one in, in its plugin.py, and app/registry.py lists them.
create_app() then adds every module without knowing anything about it.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, FastAPI

# Work that starts with the app and stops with it, such as a background
# thread. It is an async context manager. Start the work before its yield,
# and stop it in a finally block after the yield, so it still stops if
# another module fails to start:
#
#     @asynccontextmanager
#     async def lifespan(app: FastAPI) -> AsyncIterator[None]:
#         start()
#         try:
#             yield
#         finally:
#             stop()
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


@dataclass(frozen=True)
class ModuleHealth:
    """How one module is doing, shown in GET /v1/health."""

    # "degraded" when part of the module is not working.
    status: Literal["ok", "degraded"]
    # A short fixed text for the team, such as "poller stopped". Never a
    # secret or an error's own text, since GET /v1/health needs no user.
    detail: str | None = None


# A check of a module's own state. It reads only what the module keeps in
# memory, with no database or network call, so it answers at once.
HealthCheck = Callable[[], ModuleHealth]


@dataclass(frozen=True)
class Plugin:
    """What one module adds to the app."""

    # The module's folder name, such as "market".
    name: str
    # The module's routes, added under /v1. None if it has no routes yet.
    router: APIRouter | None = None
    # Work that runs while the app runs. None if there is none.
    lifespan: Lifespan | None = None
    # How the module reports its health in GET /v1/health. None if it has
    # nothing to report.
    health: HealthCheck | None = None
