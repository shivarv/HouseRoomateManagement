# House Roommate Management

A platform for roommates to manage a shared house: households, members, chores, shared expenses and bills.

## Repository layout

```
HouseRoomateManagement/
├── backend/     # Python (FastAPI) REST API + PostgreSQL — the single source of truth
├── web/         # Web client (React + TypeScript + Vite) — UI only, calls the backend API
├── ios/         # iOS client (SwiftUI) — UI only, calls the backend API
├── docs/        # Cross-cutting docs: architecture, API contract
├── docker-compose.yml   # Local PostgreSQL
└── .env.example         # Shared local environment variables
```

All business logic and data persistence live in `backend/`. The web and iOS apps are thin
clients: they never talk to the database directly, only to the REST API under `/api/v1`.

```
 ┌──────────┐      HTTPS/JSON      ┌──────────────┐      SQL      ┌────────────┐
 │  web/    │ ───────────────────▶ │   backend/   │ ────────────▶ │ PostgreSQL │
 │  ios/    │ ◀─────────────────── │   FastAPI    │ ◀──────────── │            │
 └──────────┘                      └──────────────┘               └────────────┘
```

## Getting started

1. Copy the environment file: `cp .env.example .env`
2. Start PostgreSQL: `docker compose up -d db` (runs on port **5434** so it doesn't clash with a local Postgres)
3. Start the API on port **8001** ([backend/README.md](backend/README.md)), then the web app or the iOS app.

| Part    | URL                                   |
| ------- | ------------------------------------- |
| API     | http://localhost:8001/api/v1 (Swagger at http://localhost:8001/docs) |
| Web     | http://localhost:5173                 |
| iOS     | Simulator → `localhost:8001`          |

Per-project setup:
   - [backend/README.md](backend/README.md)
   - [web/README.md](web/README.md)
   - [ios/README.md](ios/README.md)

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design and conventions
- [docs/API.md](docs/API.md) — API contract shared by web and iOS
- [docs/features/CHORE_ROTATION.md](docs/features/CHORE_ROTATION.md) — round-robin chores and today's tasks
