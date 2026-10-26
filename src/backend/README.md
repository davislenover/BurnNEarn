# FitFolio backend

The FitFolio API: a Python [FastAPI](https://fastapi.tiangolo.com) app that
the mobile app calls over HTTPS with JSON (Development Plan, Backend
Framework). Data is stored in PostgreSQL.

## Layout

| Path | What it holds |
|---|---|
| `app/main.py` | Creates the FastAPI app and adds the routes |
| `app/api/` | Routes, one module per feature area (`health.py` for now) |
| `app/core/settings.py` | Settings read from environment variables or `.env` |
| `app/core/db.py` | Database engine, sessions and the `Base` class for tables |
| `app/core/constants.py` | SRS Appendix C constants used by the backend |
| `app/models/` | Table models (none yet) |
| `migrations/` | Alembic database migrations |
| `compose.yaml` | Local PostgreSQL in Docker |
| `../../test/backend/` | Backend tests (pytest) |

## First-time setup

You need [uv](https://docs.astral.sh/uv/) and a container runtime such as
Docker Desktop or OrbStack.

```bash
cd src/backend
cp .env.example .env          # local settings, never committed
uv sync                       # installs Python 3.14 and the dependencies
docker compose up -d          # starts PostgreSQL on localhost:5432
uv run alembic upgrade head   # brings the database schema up to date
```

## Everyday commands

Run these from `src/backend`.

```bash
uv run uvicorn app.main:app --reload   # API at http://127.0.0.1:8000
uv run pytest                          # tests (needs the database running)
uv run ruff check . ../../test/backend         # lint
uv run ruff format . ../../test/backend        # format
uv run alembic revision --autogenerate -m "add <table>"   # new migration
```

With the server running, the interactive API docs are at
<http://127.0.0.1:8000/docs> and the health check is at
<http://127.0.0.1:8000/v1/health>.

## Rules

- Every route lives under `/v1`.
- Secrets (database password, Finnhub key) go in `.env` only. Never commit
  them and never send the Finnhub key to the app (HA SEC-33).
- Use the names in `app/core/constants.py` instead of literal numbers, and
  keep them in step with SRS Appendix C.
- CI (`.github/workflows/backend-ci.yml`) runs Ruff and the tests against
  PostgreSQL on every pull request.
