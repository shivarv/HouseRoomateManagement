# Architecture

## Overview

Three independently deployable projects in one repository:

| Project    | Role                                   | Tech                           |
| ---------- | -------------------------------------- | ------------------------------ |
| `backend/` | REST API, business logic, persistence  | Python, FastAPI, PostgreSQL    |
| `web/`     | Browser frontend                       | React, TypeScript, Vite        |
| `ios/`     | Native mobile frontend                 | Swift, SwiftUI                 |

The backend is the single source of truth. Clients are stateless with respect to business
data — they render what the API returns and send user actions back to it.

## Principles

1. **Clients never touch the database.** Every read/write goes through the API.
2. **Business rules live in the backend only** (e.g. expense splitting, who can edit a chore),
   so web and iOS always behave the same.
3. **One API contract** ([API.md](API.md)) is shared by both clients. Changing a response shape
   means updating the backend schema, `web/src/types/`, and `ios/RoommateApp/Core/Models/` together.
4. **Versioned API**: all routes live under `/api/v1`. Breaking changes go to `/api/v2`.

## Cross-cutting conventions

| Topic          | Convention                                                              |
| -------------- | ----------------------------------------------------------------------- |
| Transport      | JSON over HTTPS                                                         |
| JSON keys      | `snake_case` (iOS decodes with `.convertFromSnakeCase`)                 |
| IDs            | UUID strings                                                            |
| Timestamps     | ISO-8601, UTC (e.g. `2026-10-19T14:00:00Z`)                             |
| Money          | Integer cents + ISO currency code (`amount_cents: 1250, currency: "USD"`) — never floats |
| Auth           | `Authorization: Bearer <JWT>` on every request except login/register    |
| Errors         | `{ "detail": "message" }` with proper HTTP status (FastAPI default)     |
| Pagination     | `?limit=&offset=` on list endpoints                                     |

## Environments

| Env   | Backend                     | Database                    |
| ----- | --------------------------- | --------------------------- |
| Local | `uvicorn` on `:8001`        | Docker `postgres:16` on `:5434` |
| Prod  | TBD                         | Managed PostgreSQL (TBD)    |
