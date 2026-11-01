# FitFolio backend

The FitFolio API: a Python [FastAPI](https://fastapi.tiangolo.com) app that
the mobile app calls over HTTPS with JSON (Development Plan, Backend
Framework). Data is stored in PostgreSQL.

## Layout

| Path | What it holds |
|---|---|
| `app/main.py` | Creates the FastAPI app and adds the routes |
| `app/api/` | Routes, one module per feature area (`health.py` for now), and the `Money` type in `common.py` |
| `app/<feature>/` | Services: the rules for one feature, such as `app/market/` |
| `app/core/settings.py` | Settings read from environment variables or `.env` |
| `app/core/db.py` | Database engine, sessions and the `Base` class for tables |
| `app/core/constants.py` | SRS Appendix C constants used by the backend |
| `app/core/errors.py` | `DomainError`, the base class for refusing a request |
| `app/models/` | Table models |
| `migrations/` | Alembic database migrations |
| `compose.yaml` | Local PostgreSQL in Docker |
| `../../test/backend/` | Backend tests (pytest) |

## How a feature is built

Every feature has the same three layers, each with one job. A request goes
from the route, to the service, to the tables.

| Layer | Where | Its job | It never |
|---|---|---|---|
| Route | `app/api/` | Reads the request, calls a service, saves the changes once, returns JSON | Holds business rules |
| Service | `app/<feature>/` | Holds all the rules, and takes a database session | Saves changes, or deals with HTTP |
| Table | `app/models/`, `migrations/` | Describes the data and guards it, for example no negative prices | Holds logic |

A service makes its changes but doesn't save them for good. Only the route does
that, by calling `db.commit()`. This way, one route can call two services and
save both results together, or neither. For example, a buy lowers the balance
and adds the shares, and it can never do just one of those.

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
uv run alembic check                   # do the models match the migrations?
```

With the server running, the interactive API docs are at
<http://127.0.0.1:8000/docs> and the health check is at
<http://127.0.0.1:8000/v1/health>.

## Migrations

Each migration names the one before it, so they form one chain, numbered
0001, 0002, 0003 and so on.

To add one, change the models in `app/models/` (import a new module in
`app/models/__init__.py`), then run this with the next number. Without
`--rev-id`, Alembic picks a random name instead of a number.

```bash
uv run alembic heads                   # shows the newest number
uv run alembic revision --autogenerate --rev-id 0004 -m "wallet"
```

Read the new file before using it, because Alembic can miss things. Then
apply it, undo it and apply it again, as CI does:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

### Right before merging

Someone else may have merged a migration while you were working. If your
migration still comes after an old one, the chain splits in two and Alembic
stops working for everyone. So do this right before you merge:

1. While your branch still has your migration, undo it on your database. If
   you skip this, your database will wrongly count someone else's migration
   as already applied.

   ```bash
   uv run alembic downgrade -1
   ```
2. Bring in the latest `main`:

   ```bash
   git fetch origin
   git rebase origin/main
   ```
3. If `main` now has a newer migration, point your `down_revision` at it and
   take the next number: change `revision` and the file name too.
4. Check it, then push. A rebase rewrites your branch, so the push needs
   `--force-with-lease`.

   ```bash
   uv run pytest
   uv run alembic upgrade head
   git push --force-with-lease
   ```

## Tests

`uv run pytest` only ever runs on a database whose name ends in `_test`, which
it rebuilds from the migrations on every run. Your own data in `fitfolio` is
not touched. Tests ask for what they need by name:

| Fixture | What it gives a test |
|---|---|
| `client` | Sends HTTP requests to the app, and routes use `db_session` |
| `db_session` | A database session whose changes are all undone when the test ends |
| `database` | Just the rebuilt database, for tests that open their own connection |

`test/backend/conftest.py` lists a few things to watch for when using them.

## Rules

- Every route lives under `/v1`.
- Send amounts to the phone with the `Money` type, as text with 4 decimals.
- To refuse a request, raise a subclass of `DomainError`. Its name must end in
  `Error`. The phone gets `{"detail": {"code": ..., "message": ...}}`.
- Secrets (database password, Finnhub key) go in `.env` only. Never commit
  them and never send the Finnhub key to the app (HA SEC-33).
- Use the names in `app/core/constants.py` instead of literal numbers, and
  keep them in step with SRS Appendix C.
- CI (`.github/workflows/backend-ci.yml`) runs Ruff, the migration checks and
  the tests against PostgreSQL on every pull request.
