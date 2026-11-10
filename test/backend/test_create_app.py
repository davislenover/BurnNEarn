"""Tests for create_app() and the module registry."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.plugins import ModuleHealth, Plugin
from app.main import create_app
from app.registry import PLUGINS


def fine() -> ModuleHealth:
    return ModuleHealth(status="ok")


def test_a_lifespan_without_a_health_check_is_refused() -> None:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield

    with pytest.raises(ValueError, match="no health check"):
        Plugin(name="silent", lifespan=lifespan)


def test_lifespans_start_in_order_and_stop_in_reverse() -> None:
    events: list[str] = []

    def tracked(name: str):
        @asynccontextmanager
        async def lifespan(_: FastAPI) -> AsyncIterator[None]:
            events.append(f"start {name}")
            try:
                yield
            finally:
                events.append(f"stop {name}")

        return lifespan

    app = create_app(
        [
            Plugin(name="first", lifespan=tracked("first"), health=fine),
            Plugin(name="second", lifespan=tracked("second"), health=fine),
        ]
    )

    with TestClient(app):
        assert events == ["start first", "start second"]

    assert events == [
        "start first",
        "start second",
        "stop second",
        "stop first",
    ]


def test_every_registered_module_has_a_unique_name() -> None:
    names = [plugin.name for plugin in PLUGINS]

    assert len(names) == len(set(names))
