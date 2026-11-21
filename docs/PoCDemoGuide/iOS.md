# Run the PoC demo on an iPhone with a Mac

This guide gets the proof of concept running end to end: the server on a Mac,
and the app on a real iPhone that reaches the server over Wi-Fi. At the end,
your steps turn into credits on the server, and you can buy a share and see it
in the portfolio.

Steps 1 to 9 are for the first time. After that, see
[Every time you run the demo](#every-time-you-run-the-demo).

Run every command from the repository root unless a step says otherwise. You
will need three terminal windows: one for the server, one for the app's
bundler, and one for everything else.

## What you need

- A Mac with [Xcode](https://apps.apple.com/app/xcode/id497799835) from the App
  Store, and [Homebrew](https://brew.sh).
- An iPhone, and a cable for the first install (Wi-Fi also works once the
  phone is paired).
- An Apple ID. A free one works, but the app it signs only opens for seven
  days (see step 7).
- A Wi-Fi network that both the Mac and the iPhone join. Step 4 checks that
  the network lets them reach each other.

## 1. Install the tools (once)

1. Open Xcode once, accept the licence, and let it install its components.
   Then point the command line tools at it:

   ```bash
   sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
   ```

   This tells the terminal's build tools to use the full Xcode app, not the
   smaller Command Line Tools package, which can't build for an iPhone.
   `sudo` runs it as an administrator, so it asks for your Mac's password.

2. Install Node.js 24, CocoaPods, uv and OrbStack:

   ```bash
   brew install node@24 cocoapods uv orbstack
   brew link --force node@24
   ```

   - `brew install` installs four tools with Homebrew:
     - **Node.js 24** runs the app's build tools and its bundler.
     - **CocoaPods** installs the iOS libraries the app uses.
     - **uv** runs the server's Python and installs its packages.
     - **OrbStack** runs Docker, which runs the server's database.
   - `brew link --force node@24` puts Node.js 24 on your path, so the `node`,
     `npm` and `npx` commands find it. Homebrew leaves versioned tools like
     `node@24` off the path until you link them.

   Open OrbStack once from Applications, so Docker is running. Docker Desktop
   also works.

3. In Xcode, open **Xcode > Settings > Accounts** and add your Apple ID. Xcode
   uses it to sign the app for your phone.

## 2. Get the iPhone ready (once)

1. Connect the iPhone to the Mac with a cable, unlock it, and tap **Trust**
   when it asks.
2. On the iPhone, turn on Developer Mode: **Settings > Privacy & Security >
   Developer Mode**. The phone restarts. Unlock it and tap **Turn On**.
3. Join the same Wi-Fi network as the Mac.

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

3. Start the server so the phone can reach it:

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   `uvicorn` is the web server that runs the server's code, and
   `app.main:app` is the app it runs, in `app/main.py`. `--host 0.0.0.0` lets
   other devices on the network connect, and `--port 8000` is the port the app
   connects to. Leave out
   `--reload`, so saving a file can't restart the server while the app is
   using it. If macOS asks whether to accept incoming connections, choose
   **Allow**. Leave this terminal open.

## 4. Check the phone can reach the Mac

1. Open a second terminal window, since the server is still running in the
   first one. In it, find the Mac's address on the Wi-Fi:

   ```bash
   ipconfig getifaddr en0
   ```

   This prints the Mac's address on its Wi-Fi connection (`en0` is the Wi-Fi
   on most Macs). It looks like `172.17.133.103`. The steps below call this
   `<mac address>`. If it prints nothing, try `ipconfig getifaddr en1`.

2. On the iPhone, open Safari and go to `http://<mac address>:8000/v1/health`.
   It should show `"status":"ok"`.

   If the page doesn't load, the network is keeping devices apart, which many
   public and campus networks do. Turn on the iPhone's Personal Hotspot,
   connect the Mac to it, and do this step again with the Mac's new address.

## 5. Give the demo user a starting balance

A share costs a few hundred credits, and a day of steps earns at most 300. So
give the demo user a balance first. The server only pays for
steps, so this sends 30,000 steps for each of the last five days, which pays
300 a day.

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

Today is left out, so the phone's real steps still earn credits for today.
Sending the same days again pays nothing extra, since the server only pays
what it still owes for each day. To start over, reset the demo user
(step 3.1) and run this again.

## 6. Point the app at the Mac

In the second terminal window, from the repository root:

```bash
cd src/frontend
npm ci
echo 'EXPO_PUBLIC_API_URL=http://<mac address>:8000' > .env
```

Use the address from step 4, for example
`EXPO_PUBLIC_API_URL=http://172.17.133.103:8000`.

What the commands do:

- `cd src/frontend` moves into the app's folder.
- `npm ci` installs the app's packages exactly as listed in
  `package-lock.json`, into a `node_modules` folder.
- `echo '...' > .env` writes one line into `.env`: the address the app uses
  to reach the server. `>` replaces the file if it already exists.

## 7. Build the app and put it on the iPhone

1. Make the iOS project, from `src/frontend`:

   ```bash
   LANG=en_US.UTF-8 npx expo prebuild --platform ios
   ```

   `npx` runs the Expo command-line tool that `npm ci` installed. `prebuild`
   makes the native iOS project (the `ios` folder) from `app.json` and the
   app's packages, and runs CocoaPods to install the iOS libraries.
   `LANG=en_US.UTF-8` sets the text encoding for this one command, since
   CocoaPods fails without it.

   If it asks for an iOS bundle identifier, give one of your own, such as
   `com.yourname.fitfolio`. It is saved in `app.json`. Don't commit that
   change. The `ios` folder it makes is ignored by git.

2. Open `src/frontend/ios/frontend.xcworkspace` in Xcode (the `.xcworkspace`,
   not the `.xcodeproj`).
3. Click the **frontend** project, then the **frontend** target, then
   **Signing & Capabilities**. Turn on **Automatically manage signing** and
   pick your Apple ID under **Team**.
4. At the top of the window, pick your iPhone as the run destination, unlock
   the phone, and press **Run** (the play button).
5. The first time, the iPhone refuses to open the app until you trust the
   developer: **Settings > General > VPN & Device Management**, tap your
   Apple ID, then **Trust**.

**The signing only lasts seven days with a free Apple ID.** After that, the
app won't open on the iPhone. To fix it, connect the phone, open the
workspace in Xcode and press **Run** again (steps 7.2 to 7.4). You don't need
to run `prebuild` again or change any settings, and the server's data is
kept. If the iPhone asks, trust the developer again (step 7.5).

Otherwise, you only need to build again when the app's native setup changes,
such as new packages or a change to `app.json`. Code changes and a new server
address only need the bundler (step 8).

## 8. Start the bundler and open the app

1. Open a third terminal window, from `src/frontend`:

   ```bash
   npx expo start --dev-client
   ```

   This starts the bundler on port 8081. It turns the app's TypeScript into
   JavaScript and sends it to the phone, and reloads the app when the code
   changes. `--dev-client` tells it to serve the app you built in step 7, not
   Expo's generic Expo Go app. Leave it running.

2. Open **frontend** on the iPhone. It shows the development servers it finds
   on the network. Tap the one with the Mac's address. If none appears, tap
   **Enter URL manually** and type `http://<mac address>:8081`.

3. When the phone asks to access **Motion & Fitness**, tap **Allow**, so the
   app can count steps.

## 9. Check it works

| On the phone                     | What you should see                                    |
| -------------------------------- | ------------------------------------------------------ |
| Today's steps                    | Today's step count from the phone                      |
| Balance                          | About $1,500, plus what today's steps earned           |
| Earned from steps today          | Today's credits and "100 steps = 1 credit"             |
| AAPL price                       | A price that changes within about a minute             |
| Buy one share                    | "Successful purchase", the balance drops, shares held goes up |

If you see "The price is now X. Check it and confirm again.", the price
changed since the screen last checked. The card shows the new price right
away, so press **Buy** again.

In the server's terminal, every request from the phone's address should end in
`200 OK` or `201 Created`.

## Every time you run the demo

Once the app is on the phone, starting the demo only needs:

1. Open OrbStack, and join the Mac and the iPhone to the same Wi-Fi. If the
   app was built more than seven days ago, build it again (step 7).
2. From `src/backend`, start the database with `docker compose up -d --wait`.
   Run `uv run python -m app.scripts.seed_demo reset` too if you want to start
   over (both are explained in step 3.1).
3. Start the server (step 3.3).
4. Check the Mac's address and the health page (step 4). If the address
   changed, update `src/frontend/.env` (step 6).
5. Top up the balance if you reset (step 5).
6. Start the bundler (step 8). If you changed `.env`, start it with
   `npx expo start --dev-client --clear`. `--clear` empties the bundler's
   cache, so it reads the new address from `.env`.
7. Open the app and pick the server.

## Shut down

1. Press Ctrl+C in the server's terminal and in the bundler's terminal. This
   stops the command running in that window.
2. Stop the database, from `src/backend`:

   ```bash
   docker compose down
   ```

   This stops the database and removes its container. The data is kept in a
   Docker volume, so it is still there next time. Add `-v`
   (`docker compose down -v`) to delete the data too.
