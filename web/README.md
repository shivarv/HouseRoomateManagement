# Web App — Frontend

Browser client for House Roommate Management. UI only: all data comes from the backend
REST API (`/api/v1`). No business logic or direct database access lives here.

## Stack

| Concern         | Choice                            |
| --------------- | --------------------------------- |
| Language        | TypeScript                        |
| Framework       | React 18                          |
| Build tool      | Vite                              |
| Routing         | React Router                      |
| Server state    | TanStack Query (React Query)      |
| HTTP            | `fetch` wrapper in `src/api/`     |
| Styling         | Tailwind CSS                      |
| Tests           | Vitest + React Testing Library    |
| Lint / format   | ESLint + Prettier                 |

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
│   │   ├── households.ts
│   │   ├── chores.ts
│   │   └── expenses.ts
│   ├── features/           # Feature modules, each self-contained
│   │   ├── auth/           #   components, hooks (useLogin), forms
│   │   ├── households/
│   │   ├── chores/
│   │   └── expenses/
│   ├── pages/              # Route-level screens composed from features
│   ├── routes/             # Route definitions + protected-route guard
│   ├── components/         # Shared, generic UI (Button, Modal, Input, Layout)
│   ├── hooks/              # Shared hooks not tied to one feature
│   ├── lib/                # Utilities (formatting money/dates, storage helpers)
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

## Planned screens

| Route                      | Screen                              |
| -------------------------- | ----------------------------------- |
| `/login`, `/register`      | Authentication                      |
| `/households`              | List / create / join households     |
| `/households/:id`          | Household dashboard (members, summary) |
| `/households/:id/chores`   | Chore board                         |
| `/households/:id/expenses` | Expenses and balances               |

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
| `VITE_API_BASE_URL` | Backend API base URL       | `http://localhost:8000/api/v1`  |

## Common commands

```bash
npm run dev       # dev server
npm run build     # production build to dist/
npm run test      # unit tests
npm run lint      # lint
```
