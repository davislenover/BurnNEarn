"""FastAPI application: run with `uv run uvicorn app.main:app --reload`."""

from fastapi import FastAPI

from app.api import health

app = FastAPI(title="FitFolio API", version="0.1.0")

# Every route is versioned under /v1 so the app and the API can change
# separately later.
app.include_router(health.router, prefix="/v1")
