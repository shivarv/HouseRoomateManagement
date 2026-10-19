# iOS App — SwiftUI

Native iOS client for House Roommate Management. UI only: all data comes from the backend
REST API (`/api/v1`). No business logic or direct database access lives here.

## Stack

| Concern        | Choice                                         |
| -------------- | ---------------------------------------------- |
| Language       | Swift 5.10+                                    |
| UI             | SwiftUI                                        |
| Min iOS        | iOS 17                                         |
| Architecture   | MVVM (`@Observable` view models)               |
| Networking     | `URLSession` + `async/await`, `Codable`        |
| Token storage  | Keychain                                       |
| Dependencies   | Swift Package Manager (none required to start) |
| Tests          | XCTest / Swift Testing                         |

## Folder structure

```
ios/
├── RoommateApp.xcodeproj
├── RoommateApp/
│   ├── App/
│   │   ├── RoommateApp.swift      # @main entry; injects shared services into the environment
│   │   └── RootView.swift         # Switches between auth flow and main tab view
│   ├── Features/                  # One folder per feature, each with Views + ViewModels
│   │   ├── Auth/                  #   LoginView, RegisterView, AuthViewModel
│   │   ├── Households/
│   │   ├── Chores/
│   │   └── Expenses/
│   ├── Core/
│   │   ├── Networking/            # APIClient, Endpoint, APIError — the ONLY layer that calls the backend
│   │   ├── Models/                # Codable DTOs mirroring backend schemas
│   │   └── Services/              # AuthService, HouseholdService, ... (wrap APIClient per resource)
│   ├── Shared/
│   │   └── Components/            # Reusable SwiftUI views (buttons, rows, empty states)
│   └── Resources/                 # Assets.xcassets, Config (.xcconfig), Localizable strings
└── RoommateAppTests/              # Unit tests (view models, services with mocked APIClient)
```

### Data flow (MVVM)

```
View ──▶ ViewModel (@Observable) ──▶ Service (protocol) ──▶ APIClient ──▶ backend
  ▲             │
  └── state ◀───┘
```

- **Views** are declarative and dumb: render state, forward user actions to the view model.
- **ViewModels** hold screen state (`isLoading`, `items`, `error`) and call services.
- **Services** are protocols (e.g. `ChoreServiceProtocol`) so view models can be tested with mocks.
- **APIClient** handles base URL, JSON encoding/decoding (ISO-8601 dates, snake_case ↔ camelCase),
  attaches `Authorization: Bearer <token>` from Keychain, and maps errors to `APIError`.
- **Models** must match backend response schemas (see [docs/API.md](../docs/API.md)).

## Planned screens

| Tab / Flow   | Screens                                        |
| ------------ | ---------------------------------------------- |
| Auth         | Login, Register                                |
| Households   | List, Create/Join, Household detail (members)  |
| Chores       | Chore list, Chore detail / assign / complete   |
| Expenses     | Expense list, Add expense, Balances            |
| Profile      | Account, Sign out                              |

## Local setup

1. Start the backend (see [backend/README.md](../backend/README.md)).
2. Open `ios/RoommateApp.xcodeproj` in Xcode 16+.
3. Select an iOS Simulator and run (⌘R).

> The Xcode project is not created yet. Create it in Xcode with
> **File ▸ New ▸ Project ▸ iOS App** (Interface: SwiftUI, name: `RoommateApp`) saved into `ios/`,
> then move files into the folders above.

## Configuration

The API base URL is set per build configuration via `Resources/Config/*.xcconfig` → `Info.plist`
key `API_BASE_URL`:

| Configuration | `API_BASE_URL`                         |
| ------------- | -------------------------------------- |
| Debug         | `http://localhost:8000/api/v1`         |
| Release       | Production API URL                     |

The Simulator can reach `localhost` directly. On a physical device use your Mac's LAN IP, and
allow plain HTTP for local development only (App Transport Security exception in Debug).
