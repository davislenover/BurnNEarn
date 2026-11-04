# FitFolio frontend

The FitFolio mobile app uses React Native, TypeScript, and Expo for
iOS and Android.

The current setup contains a starter screen and folders for future
features. Authentication, fitness tracking, portfolio screens,
navigation, and backend integration are not implemented yet.

## Layout

| Path | What it holds |
|---|---|
| `app/App.tsx` | Main app component; currently displays the starter screen |
| `app/screens/auth/` | Login and registration screens |
| `app/screens/dashboard/` | Main overview screen |
| `app/screens/fitness/` | Fitness activity and rewards screens |
| `app/screens/portfolio/` | Portfolio, trading, and history screens |
| `app/components/` | Reusable buttons, cards, and other interface elements |
| `app/navigation/` | Navigation between screens |
| `app/services/api/` | Requests to the Python backend |
| `app/services/health/` | HealthKit and Health Connect integration |
| `app/types/` | Shared TypeScript data definitions |
| `app/theme/` | Shared colours, spacing, and text styles |
| `assets/` | App icons and images |
| `index.ts` | Registers and starts the app |
| `app.json` | App name, icons, and iOS/Android settings |
| `package.json` | Dependencies and development commands |
| `package-lock.json` | Exact dependency versions managed by npm |
| `tsconfig.json` | TypeScript configuration |
| `.gitignore` | Files and folders excluded from Git |
| `LICENSE` | Expo template licence and attribution |
| `README.md` | Frontend setup and development instructions |

The feature folders currently contain `.gitkeep` placeholders so Git
includes them before feature code is added. 

