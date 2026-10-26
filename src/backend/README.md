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

You need two tools:

- [uv](https://docs.astral.sh/uv/), which installs Python 3.14 and the
  backend's packages.
- Something that runs `docker compose`, which starts PostgreSQL from
  `compose.yaml`. Everyone uses the same `compose.yaml`, whichever app runs
  it.

### macOS

1. Install the tools with [Homebrew](https://brew.sh):

   ```bash
   brew install uv
   brew install orbstack
   ```

   Open OrbStack once from Applications so it can finish setting up.
   Docker Desktop also works if you prefer it.
2. Set up the backend, from the repository root:

   ```bash
   cd src/backend
   cp .env.example .env          # local settings, never committed
   uv sync                       # installs Python 3.14 and the packages
   docker compose up -d          # starts PostgreSQL on localhost:5432
   uv run alembic upgrade head   # brings the database schema up to date
   ```

### Windows 10/11

1. Install the tools in PowerShell:

   ```powershell
   winget install --id astral-sh.uv -e
   winget install --id Docker.DockerDesktop -e
   ```

   Start Docker Desktop and follow its prompts. It uses WSL 2, which it
   can set up for you (this works on Windows Home too). Open a new
   PowerShell window afterwards so the `uv` and `docker` commands are
   found.
2. Set up the backend, from the repository root:

   ```powershell
   cd src\backend
   Copy-Item .env.example .env   # local settings, never committed
   uv sync                       # installs Python 3.14 and the packages
   docker compose up -d          # starts PostgreSQL on localhost:5432
   uv run alembic upgrade head   # brings the database schema up to date
   ```

To check it worked, run `docker compose ps`: the `db` service should show
as healthy.

## Everyday commands

Run these from `src/backend`. They are the same on macOS and Windows.

```bash
docker compose up -d                   # start PostgreSQL
docker compose down                    # stop it (data is kept)
uv run uvicorn app.main:app --reload   # API at http://127.0.0.1:8000
uv run pytest                          # tests (needs the database running)
uv run ruff check --config pyproject.toml . ../../test/backend    # lint
uv run ruff format --config pyproject.toml . ../../test/backend   # format
uv run alembic upgrade head            # apply new migrations
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
