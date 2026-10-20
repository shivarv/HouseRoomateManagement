# iOS App — SwiftUI

Native iOS client for House Roommate Management. UI only: all data comes from the backend
REST API (`/api/v1`). No business logic or direct database access lives here.

## Stack

| Concern        | Choice                                         |
| -------------- | ---------------------------------------------- |
| Language       | Swift 5.10+                                    |
| UI             | SwiftUI                                        |
| Min iOS        | iOS 17                                         |
| Architecture   | MVVM (`@Observable` view models, `@MainActor`) |
| Networking     | `URLSession` + `async/await`, `Codable`        |
| Token storage  | Keychain                                       |
| Dependencies   | Swift Package Manager (none required to start) |

## Folder structure

```
ios/
├── RoommateApp.xcodeproj
├── RoommateApp/
│   ├── App/
│   │   ├── RoommateApp.swift      # @main entry; puts Session into the environment
│   │   └── RootView.swift         # Auth flow vs. tabs (Today · Households · Profile)
│   ├── Features/                  # One folder per feature, each with Views + ViewModels
│   │   ├── Auth/                  #   AuthView + AuthViewModel (login / register)
│   │   ├── Today/                 #   MyDayView — "Your tasks today", the reminder
│   │   ├── Households/            #   list, create/join sheets, detail tabs, rotation editor
│   │   └── Profile/
│   ├── Core/
│   │   ├── Networking/            # APIClient, APIError, TokenStore (Keychain) — the ONLY layer that calls the backend
│   │   ├── Models/                # Codable DTOs mirroring backend schemas
│   │   └── Services/              # APIClient extensions per resource + Session (signed-in user)
│   ├── Shared/
│   │   └── Components/            # TaskRow, Badge, ErrorBanner, date formatting
│   └── Resources/                 # Assets.xcassets, Info.plist (API_BASE_URL)
```

### Data flow (MVVM)

```
View ──▶ ViewModel (@Observable) ──▶ APIClient (+ service extensions) ──▶ backend
  ▲             │
  └── state ◀───┘
```

- **Views** are declarative and dumb: render state, forward user actions to the view model.
- **ViewModels** hold screen state (`isLoading`, `items`, `error`) and call services.
- **Services** are `APIClient` extensions grouped per resource (auth, households, chores/tasks).
- **APIClient** handles base URL, JSON encoding/decoding (ISO-8601 dates, snake_case ↔ camelCase),
  attaches `Authorization: Bearer <token>` from Keychain, and maps errors to `APIError`.
- **Models** must match backend response schemas (see [docs/API.md](../docs/API.md)).

## Screens

| Tab / Flow   | Screens                                        |
| ------------ | ---------------------------------------------- |
| Auth         | Login, Register                                |
| Today        | My tasks today + missed ones, Done / Undo, refreshes when the app opens |
| Households   | List, Create / Join with code, detail with Today · Schedule · People · Chores |
| Chore        | Rotation order: drag to reorder, swipe to skip, add people, pause / delete |
| Profile      | Account, server URL, Sign out                  |

## Local setup

1. Start the backend (see [backend/README.md](../backend/README.md)).
2. Open `ios/RoommateApp.xcodeproj` in Xcode 16+.
3. Select an iPhone Simulator and run (⌘R).

The project uses folder-synced groups, so any `.swift` file you add under `RoommateApp/` is
compiled automatically, with no project-file edits. To run on a real iPhone, pick your team under
**Signing & Capabilities** and change the bundle ID from `com.example.roommates`.

## Configuration

The API base URL is the `API_BASE_URL` key in
[RoommateApp/Resources/Info.plist](RoommateApp/Resources/Info.plist). The default is
`http://localhost:8001/api/v1`.

The Simulator can reach `localhost` directly. On a physical device use your Mac's LAN IP, and
allow plain HTTP for local development only (App Transport Security exception in Debug).
