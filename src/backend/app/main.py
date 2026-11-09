"""FastAPI application: run with `uv run uvicorn app.main:app --reload`."""

from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core import routes
from app.core.errors import DomainError
from app.core.plugins import Plugin
from app.registry import PLUGINS


def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
    """Send any DomainError to the phone in the same shape."""
    return JSONResponse(
        status_code=error.status,
        content={"detail": {"code": error.code, "message": error.message}},
    )


def handle_validation_error(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    """Send a request that doesn't fit its route as 422, like FastAPI does,
    but without the values that were sent.

    FastAPI's own handler sends each refused value back. Some can't be
    written as JSON, such as NaN in a body, so the phone got a 500 instead.
    """
    errors = [
        {key: value for key, value in found.items() if key != "input"}
        for found in error.errors()
    ]
    return JSONResponse(
        status_code=422, content={"detail": jsonable_encoder(errors)}
    )


def create_app(plugins: Sequence[Plugin] = PLUGINS) -> FastAPI:
    """Build the app from the modules in app/registry.py.

    Tests can pass their own plugins to build a smaller app.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Start each module's work in order. The exit stack stops them in
        # reverse order when the app shuts down, even if one fails to start.
        async with AsyncExitStack() as stack:
            for plugin in plugins:
                if plugin.lifespan is not None:
                    await stack.enter_async_context(plugin.lifespan(app))
            yield

    app = FastAPI(title="FitFolio API", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)

    # Every route is versioned under /v1 so the app and the API can change
    # separately later.
    app.include_router(routes.health_router(plugins), prefix="/v1")
    for plugin in plugins:
        if plugin.router is not None:
            app.include_router(plugin.router, prefix="/v1")
    return app


app = create_app()
