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
uv run python -m app.scripts.seed_demo
```

On Windows, use `Copy-Item .env.example .env` instead of `cp`.

The last command adds the PoC's demo user and their portfolio at 0. Running it
again changes nothing. To start the demo over at 0, deleting the demo user's
balance changes and everything else under their portfolio, run:

```bash
uv run python -m app.scripts.seed_demo reset
```

## Run it

From `src/backend`:

```bash
docker compose up -d
uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs> to try the API. To stop the database, run
`docker compose down`. Your data is kept.

## Run for the phone

Use this to test the app on a real Android phone, and for the demo. The phone
reaches the server on your computer through its USB cable. An Android
emulator works the same way.

**Once:** install `adb`, the Android tool that talks to the phone.

```bash
brew install android-platform-tools               # macOS
winget install --id Google.PlatformTools -e        # Windows
```

On the phone, turn on **Developer options** (tap **Build number** in
**Settings > About phone** seven times), then turn on **USB debugging** in
**Settings > System > Developer options**.

**In `.env`**, turn on:

| Setting                 | Value                                      | Why                                                       |
| ----------------------- | ------------------------------------------ | --------------------------------------------------------- |
| `DEMO_USER_ENABLED`     | `true`                                     | The PoC has no sign-in, so every request is the demo user |
| `MARKET_PROVIDER`       | `fake` to practise, `finnhub` for the demo | `finnhub` needs `FINNHUB_API_KEY`                         |
| `MARKET_POLLER_ENABLED` | `true`                                     | Keeps prices updating while the market is open            |

**Before every run**, from `src/backend`:

1. Start the database and reset the demo data, so the balance starts at 0:

   ```bash
   docker compose up -d
   uv run alembic upgrade head
   uv run python -m app.scripts.seed_demo reset
   ```

2. Start the server so other devices can reach it. Leave out `--reload`, so
   saving a file can't restart the server in the middle of a demo:

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0
   ```

3. Connect the phone with USB and accept the **Allow USB debugging?** prompt
   on it. Then, in a second terminal, forward the port, so `localhost:8000`
   on the phone reaches your computer:

   ```bash
   adb devices                      # the phone should be listed as "device"
   adb reverse tcp:8000 tcp:8000
   adb reverse tcp:8081 tcp:8081    # only for a debug build, for Metro
   ```

   The forwarding stops when the phone is unplugged, so run these again
   after you reconnect it.

4. Open <http://localhost:8000/v1/health> in the phone's browser. It should
   show `"status":"ok"`. If it doesn't load, run step 3 again.

Plain HTTP is only for the PoC, where requests go over the USB cable to your
own computer. When the server is hosted, every connection will use HTTPS
(SEC-16).

## Check your work

Run these before you push. CI runs the same checks on every pull request.

```bash
uv run pytest
uv run ruff check --config pyproject.toml . ../../test/backend
uv run ruff format --config pyproject.toml . ../../test/backend
uv run lint-imports
```

`lint-imports` checks that modules only call down the stack in
[BackendArchitecture.md](../../docs/Design/SoftArchitecture/BackendArchitecture.md),
and that `app/core/` imports no module. `test_public_files.py` checks that a
module uses another only through its `interface.py`, `queries.py` or
`types.py`.

To run one test file, name it with `-k`, for example
`uv run pytest -k test_market_poller`.

Tests use their own database, `fitfolio_test`, so your data is safe. A test
gets what it needs from `test/backend/conftest.py` by naming it as a
parameter:

| Fixture          | What it gives                                                                                                                                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `client`         | Calls the app without a server                                                                                                                                                         |
| `db_session`     | A database session whose changes are undone afterwards                                                                                                                                 |
| `at_time`        | Sets the time routes see: `at_time(OPEN)`                                                                                                                                              |
| `add_price`      | Gives a stock a price routes see: `add_price("AAPL", "101.5", quoted_at)`                                                                                                              |
| `make_portfolio` | Makes and commits a user with a live portfolio: `owner = make_portfolio(Decimal("500"))`. The 500 is one reward dated 1 Jan 2000. Pass `user=` for a given user, such as the demo user |
| `as_user`        | Makes routes see that user: `as_user(owner.user)`. Without it, a route that needs a user answers 401                                                                                   |

## Where code goes

| Path                  | What it holds                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------ |
| `app/main.py`         | Builds the app                                                                             |
| `app/registry.py`     | The list of modules. Add yours here                                                        |
| `app/core/`           | What every module shares: settings, the database, the clock, `Money`, errors and constants |
| `app/<module>/`       | One feature, such as `app/market/`                                                         |
| `migrations/`         | Changes to the database                                                                    |
| `../../test/backend/` | Tests                                                                                      |

The files inside a module, and the rules for using another module, are in
[BackendArchitecture.md](../../docs/Design/SoftArchitecture/BackendArchitecture.md#a-modules-files).

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
- Change a balance only with `wallet.interface.change_balance`, after
  `lock_live_portfolio`, and commit once in the route.
- Take the time from `app/core/clock.py`, never from `datetime.now()`.
- Use the constants in `app/core/constants.py` instead of literal numbers.
- Secrets go in `.env` only. Never send the Finnhub key to the app.
