# Web App — Frontend

Browser client for House Roommate Management. UI only: all data comes from the backend
REST API (`/api/v1`). No business logic or direct database access lives here.

## Stack

| Concern         | Choice                            |
| --------------- | --------------------------------- |
| Language        | TypeScript                        |
| Framework       | React 19                          |
| Build tool      | Vite 8                            |
| Routing         | React Router (declarative mode)   |
| Server state    | TanStack Query (React Query)      |
| HTTP            | `fetch` wrapper in `src/api/`     |
| Styling         | Tailwind CSS 4                    |

## Folder structure

```
web/
├── public/                 # Static assets served as-is (favicon, etc.)
├── src/
│   ├── main.tsx            # Entry point: providers (QueryClient, Router, Auth)
│   ├── App.tsx             # Root layout
│   ├── api/                # API client layer — the ONLY place that calls the backend
│   │   ├── client.ts       # Base fetch wrapper: base URL, auth header, error handling
│   │   ├── auth.ts         # login, register, me
│   │   ├── households.ts   # households, members, invites
│   │   └── chores.ts       # chores, rotation, schedule, tasks
│   ├── features/           # Feature modules, each self-contained
│   │   ├── auth/           #   AuthContext (signed-in user, sign in/out)
│   │   ├── households/     #   React Query hooks
│   │   └── chores/         #   React Query hooks + TaskCard
│   ├── pages/              # Route-level screens
│   │   ├── AuthPage.tsx    #   login / register
│   │   ├── MyDayPage.tsx   #   "Your tasks today" — the reminder, landing page after login
│   │   ├── HouseholdsPage.tsx   # list, create, join with invite code
│   │   └── household/      #   tabs: Today, Schedule, People, Chores (rotation editor)
│   ├── routes/             # Protected-route guard
│   ├── components/         # Shared UI (Button, Input, Card, Badge, AppShell)
│   ├── lib/                # Date formatting helpers
│   └── types/              # TypeScript types mirroring backend schemas
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

### Data flow

```
page ──▶ feature hook (useChores) ──▶ React Query ──▶ src/api/chores.ts ──▶ client.ts ──▶ backend
```

- Components never call `fetch` directly; they use feature hooks backed by `src/api/`.
- Types in `src/types/` must match the backend response schemas (see [docs/API.md](../docs/API.md)).
- Auth: access token is stored client-side and attached by `client.ts` as `Authorization: Bearer <token>`.
  A 401 response clears the session and redirects to `/login`.

## Screens

| Route                      | Screen                              |
| -------------------------- | ----------------------------------- |
| `/`                        | My day: my tasks today + missed ones |
| `/login`, `/register`      | Authentication                      |
| `/households`              | List / create / join households     |
| `/households/:id`          | Everyone's tasks today              |
| `/households/:id/schedule` | Who does what for the next 7–28 days |
| `/households/:id/people`   | Add / remove roommates, admins      |
| `/households/:id/chores`   | Chores and their rotation order     |

## Local setup

```bash
cd web
npm install
npm run dev        # http://localhost:5173
```

The backend must be running (see [backend/README.md](../backend/README.md)).

## Configuration

| Variable            | Description                | Default                         |
| ------------------- | -------------------------- | ------------------------------- |
| `VITE_API_BASE_URL` | Backend API base URL (read from the repo-root `.env`) | `http://localhost:8001/api/v1`  |

## Common commands

```bash
npm run dev       # dev server
npm run build     # production build to dist/
npm run typecheck # TypeScript check
```
