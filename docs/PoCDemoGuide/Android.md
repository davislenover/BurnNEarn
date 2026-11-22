# Run the PoC demo on Android with a Mac

This guide gets the proof of concept running end to end: the server on a Mac,
and the app on an Android emulator or an Android phone. At the end, the app
reads steps through Health Connect and turns them into credits on the server,
and you can buy a share and see it in the portfolio.

Steps 1 to 9 are for the first time. After that, see
[Every time you run the demo](#every-time-you-run-the-demo).

Run every command from the repository root unless a step says otherwise. You
will need three terminal windows: one for the server, one for the app, and one
for everything else.

## What you need

- A Mac with [Homebrew](https://brew.sh), and about 15 GB of free space for
  the Android tools and the emulator.
- Either the Android emulator, which step 2 sets up, or an Android phone with
  Android 8 or later and a USB cable (see
  [Use an Android phone instead](#use-an-android-phone-instead)).

## 1. Install the tools (once)

1. Install Java 17, Node.js 24, uv, OrbStack and Android's command-line
   tools:

   ```bash
   brew install openjdk@17 node@24 uv orbstack
   brew install --cask android-commandlinetools
   brew link --force node@24
   ```

   - `brew install` installs five tools with Homebrew:
     - **Java 17** runs Gradle, which builds the Android app. React Native's
       build tools expect Java 17, so use it even if a newer Java is
       installed.
     - **Node.js 24** runs the app's build tools and its bundler.
     - **uv** runs the server's Python and installs its packages.
     - **OrbStack** runs Docker, which runs the server's database.
     - **android-commandlinetools** installs `sdkmanager` and `avdmanager`,
       which download and set up the rest of Android's tools.
   - `brew link --force node@24` puts Node.js 24 on your path, so the `node`,
     `npm` and `npx` commands find it. Homebrew leaves versioned tools like
     `node@24` off the path until you link them.

   Open OrbStack once from Applications, so Docker is running. Docker Desktop
   also works.

2. Tell the terminal where Java and Android's tools are. Add these lines to
   the end of `~/.zshrc`, then open a new terminal window:

   ```bash
   export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
   export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
   export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
   ```

   `~/.zshrc` runs every time a terminal window opens, so these settings stay.
   `JAVA_HOME` tells Gradle to use Java 17. `ANDROID_HOME` tells the build
   where Android's tools are. The last line puts `adb`, `emulator`,
   `sdkmanager` and `avdmanager` on your path, so you can run them by name.

3. Accept Android's licences and download the tools the build and the
   emulator need:

   ```bash
   yes | sdkmanager --licenses
   sdkmanager "platform-tools" "emulator" "system-images;android-35;google_apis_playstore;arm64-v8a"
   ```

   - `sdkmanager --licenses` asks you to accept each of Android's licences.
     `yes |` answers yes to all of them. The build can't download anything
     until they are accepted.
   - The second command downloads three things: **platform-tools** (which
     has `adb`, the tool that talks to the emulator or phone), the
     **emulator**, and an **Android 15 system image**, the copy of Android
     the emulator runs. This is a large download. The Gradle build downloads
     the rest itself in step 7.

## 2. Make the emulator (once)

Skip this step if you use an Android phone.

```bash
avdmanager create avd -n FitFolio_API35 -k "system-images;android-35;google_apis_playstore;arm64-v8a" -d pixel_8
```

This makes a virtual phone named `FitFolio_API35`. `-k` picks the Android 15
image from step 1.3, and `-d pixel_8` makes it the size of a Pixel 8. If it
asks whether to make a custom hardware profile, press Enter for no. It may
also print an error about `devices.xml`. That is harmless, and the emulator is
still made.

## 3. Set up and start the server

1. Set up the server, from `src/backend`:

   ```bash
   cd src/backend
   cp .env.example .env
   uv sync
   docker compose up -d --wait
   uv run alembic upgrade head
   uv run python -m app.scripts.seed_demo reset
   ```

   What the commands do:

   - `cd src/backend` moves into the server's folder.
   - `cp .env.example .env` copies the example settings into `.env`, the file
     the server reads its settings from. Skip it if you already have a
     `.env`, since it would replace yours.
   - `uv sync` installs the Python version and the packages the server needs,
     exactly as listed in `uv.lock`.
   - `docker compose up -d --wait` starts the PostgreSQL database in Docker.
     `-d` runs it in the background, and `--wait` waits until it accepts
     connections, so the next command doesn't fail.
   - `uv run alembic upgrade head` creates the database's tables, or updates
     them to the latest version. It does nothing if they are already up to
     date.
   - `uv run python -m app.scripts.seed_demo reset` creates the demo user with
     a fresh portfolio and a balance of 0. Run it again whenever you want to
     start over.

2. Choose where prices come from, in `src/backend/.env`. Never commit `.env`.

   | Setting              | Real prices          | Made-up prices (backup) |
   | -------------------- | -------------------- | ----------------------- |
   | `MARKET_PROVIDER`    | `finnhub`            | `fake`                  |
   | `FINNHUB_API_KEY`    | your Finnhub key     | not needed              |
   | `MARKET_ALWAYS_OPEN` | `false`              | `true`                  |

   - **Real prices** only allow buying while the market is open: 9:30 AM to
     4:00 PM Eastern on trading days. The server refuses
     `MARKET_ALWAYS_OPEN=true` with real prices, so real prices are never
     shown as live while the market is closed.
   - **Made-up prices** allow buying at any time. They change every minute.
     Use them to practise, and as the backup if the market is closed or
     Finnhub is down.

   Keep these two settings on either way:

   - `DEMO_USER_ENABLED=true`: the PoC has no sign-in yet, so while this is
     on, the server treats every request as coming from the built-in demo
     user (the one step 3.1 creates). The app never sends who the user is.
     If it is off, the server refuses every request that needs a user with
     `401 Unauthorized`, and the app shows "Unavailable".
   - `MARKET_POLLER_ENABLED=true`: the server fetches new prices every minute
     while the market is open. If it is off, the server never fetches prices,
     so the price stays missing or out of date.

3. Start the server:

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   `uvicorn` is the web server that runs the server's code, and
   `app.main:app` is the app it runs, in `app/main.py`. `--port 8000` is the
   port the app connects to. `--host 0.0.0.0` also lets other devices on the
   network connect, which a phone on Wi-Fi needs. Leave out `--reload`, so
   saving a file can't restart the server while the app is using it. If macOS
   asks whether to accept incoming connections, choose **Allow**. Leave this
   terminal open.

## 4. Start the emulator and connect it to the Mac

1. Open a second terminal window, since the server is still running in the
   first one. In it, start the emulator:

   ```bash
   emulator -avd FitFolio_API35 &
   ```

   This opens the virtual phone in its own window. `&` runs it in the
   background, so you can keep using this terminal. Wait until it shows the
   Android home screen.

2. Connect the emulator's ports to the Mac:

   ```bash
   adb devices
   adb reverse tcp:8000 tcp:8000
   adb reverse tcp:8081 tcp:8081
   ```

   - `adb devices` lists the emulators and phones `adb` can reach. The
     emulator shows as `emulator-5554` with the word `device` next to it.
   - `adb reverse tcp:8000 tcp:8000` makes `localhost:8000` on the emulator
     reach port 8000 on the Mac, where the server runs. So the app can use
     `localhost` and doesn't need the Mac's address.
   - `adb reverse tcp:8081 tcp:8081` does the same for the bundler (step 8).

   The forwarding stops when the emulator closes, so run these two
   `adb reverse` commands again each time you start it.

3. In the emulator's Chrome, go to `http://localhost:8000/v1/health`. It
   should show `"status":"ok"`.

## 5. Give the demo user a starting balance

A share costs a few hundred credits, and a day of steps earns at most 300. So
give the demo user a balance first. The server only pays for steps, so this
sends 30,000 steps for each of the last five days, which pays 300 a day.

In the second terminal window, run the following. It works from any folder,
and the server must still be running in the first window:

```bash
python3 - <<'EOF'
import json, urllib.request, datetime
today = datetime.date.today()
body = {"time_zone": "America/Toronto", "totals": [
    {"activity_date": str(today - datetime.timedelta(days=i)),
     "activity_type": "steps", "step_count": 30000} for i in range(1, 6)]}
request = urllib.request.Request(
    "http://127.0.0.1:8000/v1/me/activity/daily-totals",
    data=json.dumps(body).encode(), method="PUT",
    headers={"Content-Type": "application/json"})
print(json.load(urllib.request.urlopen(request))["cash_balance"])
EOF
```

It prints `1500.0000`, the demo user's new balance.

What the code does:

- It is a short Python script, run straight from the terminal. `python3 -`
  reads the script from the lines between `<<'EOF'` and `EOF`, so there is no
  file to save.
- It builds the same request the app sends when it syncs steps: a time zone,
  and a list of daily step totals. Here the list has 30,000 steps for each of
  the five days before today (`range(1, 6)` counts back one to five days).
- It sends that request to the server's step sync route,
  `PUT /v1/me/activity/daily-totals`, on this Mac (`127.0.0.1:8000`).
- The server pays one credit for every 100 steps, up to 300 a day, so each day
  pays 300 and the five days pay 1,500. The time zone tells the server which
  day is today, so it knows the five days are in the past.
- It prints `cash_balance` from the server's reply.

Today is left out, so the app's real steps still earn credits for today.
Sending the same days again pays nothing extra, since the server only pays
what it still owes for each day. To start over, reset the demo user
(step 3.1) and run this again.

## 6. Point the app at the server

In the second terminal window, from the repository root:

```bash
cd src/frontend
npm ci
echo 'EXPO_PUBLIC_API_URL=http://localhost:8000' > .env
```

What the commands do:

- `cd src/frontend` moves into the app's folder.
- `npm ci` installs the app's packages exactly as listed in
  `package-lock.json`, into a `node_modules` folder.
- `echo '...' > .env` writes one line into `.env`: the address the app uses
  to reach the server. `localhost` works because of the `adb reverse`
  commands in step 4. `>` replaces the file if it already exists.

## 7. Build the app and put it on the emulator

Open a third terminal window, and from `src/frontend`:

```bash
npx expo run:android
```

`npx` runs the Expo command-line tool that `npm ci` installed. `run:android`
does four things:

1. It makes the native Android project (the `android` folder) from `app.json`
   and the app's packages, the first time. The folder is ignored by git.
2. It builds the app with Gradle. The first build downloads Gradle and more of
   Android's tools, so it is slow. Later builds are much faster.
3. It installs the app on the running emulator.
4. It starts the bundler and opens the app. The bundler turns the app's
   TypeScript into JavaScript and sends it to the emulator, and reloads the
   app when the code changes.

Leave this terminal running, since it is now the bundler.

You only need to build again when the app's native setup changes, such as new
packages or a change to `app.json`. Code changes and a new server address only
need the bundler (see
[Every time you run the demo](#every-time-you-run-the-demo)).

## 8. Allow step access

The first time the app opens, it asks Health Connect for access to steps:

1. Health Connect shows **Get started with Health Connect**. Tap
   **Get started**.
2. It asks whether to allow **frontend** to read **Steps**. Turn on **Steps**,
   then tap **Allow**.

Health Connect is built into Android 14 and later. On Android 13 and earlier,
install the **Health Connect** app from the Play Store first.

## 9. Check it works

| On the app                       | What you should see                                    |
| -------------------------------- | ------------------------------------------------------ |
| Today's steps                    | 0 on the emulator, which has no step data. A phone shows its real steps |
| Balance                          | About $1,500, plus what today's steps earned           |
| Earned from steps today          | Today's credits and "100 steps = 1 credit"             |
| AAPL price                       | A price that changes within about a minute             |
| Buy one share                    | "Successful purchase", the balance drops, shares held goes up |

If you see "The price is now X. Check it and confirm again.", the price
changed since the screen last checked. The card shows the new price right
away, so press **Buy** again.

In the server's terminal, every request from the app should end in `200 OK` or
`201 Created`.

## Look under the hood

While you use the app, you can watch what it sends and what the server stores.

### The server's log

The server's terminal (step 3.3) prints one line for each request the app
sends: who sent it, the route, and the result. Requests from the app start
with `127.0.0.1`, since `adb reverse` passes the app's requests through the Mac. For example:

```text
INFO:     127.0.0.1:53987 - "POST /v1/me/trades HTTP/1.1" 201 Created
```

| Route                              | When the app sends it                                    |
| ---------------------------------- | -------------------------------------------------------- |
| `PUT /v1/me/activity/daily-totals` | When it opens or comes back to the front, to sync today's steps |
| `GET /v1/me/balance`               | When it opens, to show the balance                        |
| `GET /v1/assets`                   | Every minute, and after a refused buy, to show the price  |
| `POST /v1/me/trades`               | When you press **Buy**. `201` means it bought, `409` means it was refused, such as when the price changed |
| `GET /v1/me/portfolio`             | Every minute, and after a buy, to show the portfolio      |

### Try the server's routes

Open <http://127.0.0.1:8000/docs> in the Mac's browser. It lists every route
the server has. Click one, then **Try it out** and **Execute** to send it and
see the reply. For example, `GET /v1/me/balance` shows the demo user's
balance, and `GET /v1/health` shows whether the database and the price updates
are working. A `PUT` or `POST` here changes the demo user's data, just like
the app does.

### Look inside the database

From `src/backend`:

```bash
docker compose exec db psql -U fitfolio -d fitfolio
```

`docker compose exec db` runs a command inside the database's container.
`psql` is PostgreSQL's command-line tool, and `-U fitfolio -d fitfolio` picks
the user and the database, both set in `compose.yaml`. It shows a
`fitfolio=#` prompt. Type a query, ending with a semicolon, and press Enter.
Type `\q` to quit. Only read the data here, since changing rows by hand can
leave the balance out of step with its history.

Some queries to try:

- The tables the server keeps:

  ```sql
  \dt
  ```

- The demo user's balance:

  ```sql
  SELECT cash_balance FROM portfolios;
  ```

- Each day's steps, and whether the day counted (`t` for true). A day over
  the plausibility limit doesn't count:

  ```sql
  SELECT activity_date, step_count, counted FROM activity_daily_totals ORDER BY activity_date;
  ```

- Every change to the balance. `activity_reward` is credits from a day's
  steps, and `trade_purchase` is the cost of a buy, shown as a negative
  amount. The balance always equals the sum of these changes, which
  `SELECT sum(amount) FROM balance_changes;` shows:

  ```sql
  SELECT created_at, reason, amount, activity_date FROM balance_changes ORDER BY created_at;
  ```

- Every trade, with the price paid and the balance after it:

  ```sql
  SELECT a.symbol, t.quantity, t.unit_price, t.currency_amount, t.cash_balance_after
  FROM trades t JOIN assets a USING (asset_id) ORDER BY t.created_at;
  ```

- The newest prices, and the result of each request for a price (`ok`,
  `rate_limited`, `unknown_symbol` or `error`):

  ```sql
  SELECT a.symbol, p.price, p.quoted_at FROM prices p JOIN assets a USING (asset_id)
  ORDER BY p.quoted_at DESC LIMIT 5;
  SELECT outcome, count(*) FROM provider_requests GROUP BY outcome;
  ```

Times are shown in UTC, which is what `+00` means. You can also open the
database in an app such as TablePlus or pgAdmin: connect to `localhost` on
port 5432, with the user, password and database name from
`src/backend/compose.yaml`.

## Use an Android phone instead

The steps are the same, except for step 2 and step 4:

1. On the phone, turn on **Developer options**: open **Settings > About
   phone** and tap **Build number** seven times. Then turn on
   **USB debugging** in **Settings > System > Developer options**.
2. Connect the phone to the Mac with a USB cable, and tap **Allow** when the
   phone asks **Allow USB debugging?**.
3. Skip step 2 and step 4.1. In step 4.2, `adb devices` lists the phone by its
   serial number with the word `device` next to it, and the two
   `adb reverse` commands connect the phone the same way.
4. In step 4.3, use the phone's Chrome.

`npx expo run:android` in step 7 then installs the app on the phone. If the
phone and an emulator are both connected, it asks which one to use. The
`adb reverse` forwarding only works while the cable is connected, so run the
two `adb reverse` commands again after you reconnect it.

## Every time you run the demo

Once the app is installed, starting the demo only needs:

1. Open OrbStack.
2. From `src/backend`, start the database with `docker compose up -d --wait`.
   Run `uv run python -m app.scripts.seed_demo reset` too if you want to start
   over (both are explained in step 3.1).
3. Start the server (step 3.3).
4. Start the emulator, or connect the phone, and run the two `adb reverse`
   commands (step 4).
5. Top up the balance if you reset (step 5).
6. From `src/frontend`, start the bundler with `npx expo start --dev-client`,
   then press `a` in that terminal to open the app on the emulator or phone.
   `--dev-client` tells it to serve the app you built in step 7, not Expo's
   generic Expo Go app.

## Shut down

1. Press Ctrl+C in the server's terminal and in the bundler's terminal. This
   stops the command running in that window.
2. Close the emulator's window.
3. Stop the database, from `src/backend`:

   ```bash
   docker compose down
   ```

   This stops the database and removes its container. The data is kept in a
   Docker volume, so it is still there next time. Add `-v`
   (`docker compose down -v`) to delete the data too.
