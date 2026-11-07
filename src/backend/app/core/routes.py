"""The kernel's own route: the health check, used by developers and CI to
see that the API is up and how each module is doing."""

import logging
from collections.abc import Sequence
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.plugins import HealthCheck, ModuleHealth, Plugin

logger = logging.getLogger(__name__)


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    # The health of each module that has a health check, by name.
    modules: dict[str, ModuleHealth]


def health_router(plugins: Sequence[Plugin]) -> APIRouter:
    """The health route, reporting the database and each module in plugins.

    create_app() builds one for its own plugins, so the route never has to
    know which modules exist.
    """
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health(response: Response, db: Session = Depends(get_db)) -> Health:
        """Report whether the API can reach the database, and how each
        module is doing."""
        database: Literal["ok", "unavailable"] = "ok"
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            database = "unavailable"
            # Nothing works without the database. A degraded module still
            # gets 200, since the rest of the API still works.
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        modules = {
            plugin.name: _check(plugin.name, plugin.health)
            for plugin in plugins
            if plugin.health is not None
        }
        healthy = database == "ok" and all(
            module.status == "ok" for module in modules.values()
        )
        return Health(
            status="ok" if healthy else "degraded",
            database=database,
            modules=modules,
        )

    return router


def _check(name: str, health: HealthCheck) -> ModuleHealth:
    try:
        return health()
    except Exception:
        # The error goes to the log only. Its text could say too much, and
        # the route needs no signed-in user.
        logger.exception("The health check of %s failed", name)
        return ModuleHealth(status="degraded", detail="health check failed")
