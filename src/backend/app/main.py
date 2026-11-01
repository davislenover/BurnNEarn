"""FastAPI application: run with `uv run uvicorn app.main:app --reload`."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import health
from app.core.errors import DomainError

app = FastAPI(title="FitFolio API", version="0.1.0")


@app.exception_handler(DomainError)
def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
    """Send any DomainError to the phone in the same shape."""
    return JSONResponse(
        status_code=error.status,
        content={"detail": {"code": error.code, "message": error.message}},
    )


# Every route is versioned under /v1 so the app and the API can change
# separately later.
app.include_router(health.router, prefix="/v1")
