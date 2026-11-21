# PoC demo guide

The proof of concept is two programs: a server that runs on a Mac, and the
FitFolio app on a phone that talks to it. The app reads the day's steps, the
server turns them into credits, and the user can buy a share with them and see
it in the portfolio.

There is one step by step guide for each kind of phone:

| Guide                    | Runs the app on                         |
| ------------------------ | --------------------------------------- |
| [iOS.md](iOS.md)         | an iPhone, built and installed from a Mac |
| [Android.md](Android.md) | the Android emulator on a Mac, or an Android phone |

Both guides set up the server the same way (steps 3 and 5 are the same in
each). They differ in how the app is built, how it reaches the server, and how
it reads steps. Each guide also has a **Look under the hood** section, on
reading the server's log, trying its routes and looking inside the database.

## How each version works

|                          | iOS                                     | Android |
| ------------------------ | --------------------------------------- | ------- |
| How the app reads steps  | Core Motion, through Expo's Pedometer   | Health Connect |
| How it reaches the server | Over Wi-Fi, at the Mac's address        | Through `adb reverse`, at `localhost` |
| How it is built          | Xcode, signed with your Apple ID        | Gradle, through `npx expo run:android` |
| What can expire          | The signing, after seven days with a free Apple ID | Nothing |

## What versions are needed

These are the minimums the app's setup asks for. Only the versions in
[What was tested](#what-was-tested) have been tried.

The app is built with Expo SDK 58 and React Native 0.88.

### iOS

- **iPhone:** iOS 16.4 or later. Expo's modules need 16.4, which is newer
  than React Native's own minimum of 15.1, so 16.4 is the floor. Every iPhone
  that runs iOS 16.4 has the motion chip that counts steps.
- **Mac:** a version of Xcode new enough to support the iPhone's iOS version.
  Recent versions of Xcode need a recent macOS, so an older Mac may not be
  able to run one.
- **Apple ID:** a free one works, but the app it signs only opens for seven
  days. A paid Apple Developer account signs it for a year.

### Android

- **Phone or emulator:** Android 8.0 (API 26) or later, which is the app's
  minimum. The app targets Android 16 (API 36).
- **Health Connect:** built into Android 14 and later. On Android 8 to 13, the
  Health Connect app has to be installed from the Play Store.
- **Mac:** Java 17 to run the build, and Android's command-line tools. The
  emulator's system image has to match the Mac's chip: `arm64-v8a` on an Apple
  silicon Mac (as in the guide), `x86_64` on an Intel Mac.

### The server (both)

- Python 3.14, which `uv` installs.
- PostgreSQL 18, which Docker runs.
- For real prices, a Finnhub API key. Made-up prices need nothing.

## What was tested

All on one Mac, on November 20, 2026:

| Part         | Version                                       |
| ------------ | --------------------------------------------- |
| Mac          | macOS 27.0.1, Apple silicon                   |
| Xcode        | 27.0                                          |
| Node.js      | 24.22.3                                       |
| Java         | 17.0.21 (for Android)                         |

| Device | OS | How it was built | What worked |
| ------ | -- | ---------------- | ----------- |
| iPhone 16 Pro (a real phone) | iOS 27.2.1 | `xcodebuild` from the terminal, then installed with `devicectl` | Reached the server over a public Wi-Fi network. Balance, price, buying a share, and buying again after the price changed. Earlier the same week, real steps synced and 100 steps became one credit. |
| iPhone 16 Pro simulator | iOS 18.5 | `npx expo run:ios` | Balance, price, buying, and buying again after the price changed. Steps showed "Unavailable", since the simulator has no motion sensor. |
| Android emulator, Pixel 8 profile | Android 15 (API 35), Google Play image, `arm64-v8a` | `npx expo run:android` | Health Connect asked for and got access to steps, the sync went through with 0 steps (the emulator has no step data), and balance, price and buying two shares worked. |

Every run used made-up prices with the market forced open
(`MARKET_PROVIDER=fake`, `MARKET_ALWAYS_OPEN=true`).

## What was not tested

- **An Android phone.** The [Use an Android phone instead](Android.md#use-an-android-phone-instead)
  part of the Android guide follows the server's README, but no phone was
  tried.
- **Real steps on Android.** The emulator only read 0 steps.
- **Real prices from Finnhub** in these runs.
- **The Xcode Run button.** The iOS guide uses it because it is the simplest
  way, but the tested build used `xcodebuild` from the terminal, which does the
  same build.
- **`npx expo run:android` starting the bundler itself.** The tested run
  started the bundler in a separate window.
- **Intel Macs, and iOS or Android versions other than the ones above.**
