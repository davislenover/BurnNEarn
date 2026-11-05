# FitFolio backend

The FitFolio API: a Python [FastAPI](https://fastapi.tiangolo.com) app that
the phone calls over HTTPS with JSON. Data is stored in PostgreSQL.

How the code is organised is explained in
[BackendArchitecture.md](../../docs/Design/SoftArchitecture/BackendArchitecture.md).

## Set up (once)

You need two tools: [uv](https://docs.astral.sh/uv/) for Python, and Docker
for the database.

**macOS**

```bash
brew install uv orbstack
```

Open OrbStack once from Applications. Docker Desktop also works.

**Windows (PowerShell)**

```powershell
winget install --id astral-sh.uv -e
winget install --id Docker.DockerDesktop -e
```

Start Docker Desktop, then open a new PowerShell window.

**Then, from the repository root**

```bash
cd src/backend
cp .env.example .env
uv sync
docker compose up -d
uv run alembic upgrade head
```

On Windows, use `Copy-Item .env.example .env` instead of `cp`.

## Run it

From `src/backend`:

```bash
docker compose up -d
uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs> to try the API. To stop the database, run
`docker compose down`. Your data is kept.

## Check your work

Run these before you push. CI runs the same checks on every pull request.

```bash
uv run pytest
uv run ruff check --config pyproject.toml . ../../test/backend
uv run ruff format --config pyproject.toml . ../../test/backend
```

Tests use their own database, `fitfolio_test`, so your data is safe. A test
asks for `client` to call the app, or `db_session` for a database session
whose changes are undone afterwards.

## Where code goes

| Path | What it holds |
|---|---|
| `app/main.py` | Builds the app |
| `app/registry.py` | The list of modules. Add yours here |
| `app/core/` | What every module shares: settings, the database, the clock, `Money`, errors and constants |
| `app/<module>/` | One feature, such as `app/market/` |
| `migrations/` | Changes to the database |
| `../../test/backend/` | Tests |

Inside a module, leave out any file it doesn't need:

| File | What goes in it |
|---|---|
| `interface.py` | Functions other modules may call |
| `queries.py` | Reads other modules may call |
| `types.py` | Data classes and errors |
| `service.py` | The rules. Never commits |
| `models.py` | The tables |
| `routes.py` | The HTTP routes. Commits once |
| `plugin.py` | Adds the module to the app |

Other modules may only import `interface.py`, `queries.py` and `types.py`.

## Change the database

1. Change your module's `models.py`.
2. Make a migration named after your module, numbered from 0001:

   ```bash
   uv run alembic revision --autogenerate --rev-id wallet_0001 -m "wallet"
   ```

3. Read the new file, then apply it:

   ```bash
   uv run alembic upgrade head
   ```

If `main` gets a new migration while you work, run
`uv run alembic downgrade -1`, rebase on `main`, set your migration's
`down_revision` to `main`'s newest migration, then run
`uv run alembic upgrade head` again.

## Rules

- Every route is under `/v1`.
- Send amounts to the phone with the `Money` type.
- To refuse a request, raise a subclass of `DomainError`.
- Take the time from `app/core/clock.py`, never from `datetime.now()`.
- Use the constants in `app/core/constants.py` instead of literal numbers.
- Secrets go in `.env` only. Never send the Finnhub key to the app.
