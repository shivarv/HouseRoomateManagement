# API Contract (v1)

Base URL: `/api/v1`. The live, authoritative spec is served by the backend at `/docs` (Swagger)
and `/openapi.json`. This file is the human-readable plan both clients build against.

Status: **implemented** for health, auth, households, members, chores and tasks. Expenses are still planned.

## Health

| Method | Path      | Auth | Description              |
| ------ | --------- | ---- | ------------------------ |
| GET    | `/health` | No   | API + database liveness  |

## Auth

| Method | Path             | Auth | Description                         |
| ------ | ---------------- | ---- | ----------------------------------- |
| POST   | `/auth/register` | No   | Create account                      |
| POST   | `/auth/login`    | No   | Returns `{ access_token, token_type }` |
| GET    | `/auth/me`       | Yes  | Current user                        |

## Households

| Method | Path                                  | Description                  |
| ------ | ------------------------------------- | ---------------------------- |
| GET    | `/households`                         | Households I belong to       |
| POST   | `/households`                         | Create household             |
| GET    | `/households/{id}`                    | Household detail + members   |
| PATCH  | `/households/{id}`                    | Rename / change timezone (admin) |
| GET    | `/invites/{code}`                     | Preview: household + names not yet claimed |
| POST   | `/invites/{code}/accept`              | Join: `{ member_id }` claims a name, `{}` joins as new person |

## Members

| Method | Path                         | Description                      |
| ------ | ---------------------------- | -------------------------------- |
| GET    | `/households/{id}/members`   | List people in the house         |
| POST   | `/households/{id}/members`   | Add a person `{ display_name }`  |
| PATCH  | `/members/{member_id}`       | Rename / change role (admin)     |
| DELETE | `/members/{member_id}`       | Remove from house + all rotations (admin) |

## Chores & tasks (round-robin rotation)

Full design: [features/CHORE_ROTATION.md](features/CHORE_ROTATION.md)

| Method | Path                                  | Description                                   |
| ------ | ------------------------------------- | --------------------------------------------- |
| GET    | `/households/{id}/chores`             | List chores with rotation order               |
| POST   | `/households/{id}/chores`             | Create chore `{ name, frequency, member_ids }`|
| PATCH  | `/chores/{chore_id}`                  | Rename / deactivate                           |
| PUT    | `/chores/{chore_id}/rotation`         | Replace rotation order `{ member_ids }`       |
| DELETE | `/chores/{chore_id}`                  | Delete chore                                  |
| GET    | `/households/{id}/schedule?from=&days=` | Who has which chore on each day (max 31 days) |
| GET    | `/households/{id}/tasks/today`        | Everyone's tasks today                        |
| GET    | `/me/tasks/today`                     | My tasks today (the in-app reminder)          |
| POST   | `/tasks/{task_id}/complete`           | Mark a task done (assignee or admin)          |
| POST   | `/tasks/{task_id}/reopen`             | Undo "done"                                   |

## Expenses

| Method | Path                               | Description                         |
| ------ | ---------------------------------- | ----------------------------------- |
| GET    | `/households/{id}/expenses`        | List expenses                       |
| POST   | `/households/{id}/expenses`        | Add expense (with splits)           |
| GET    | `/households/{id}/balances`        | Who owes whom                       |
| PATCH  | `/expenses/{expense_id}`           | Edit expense                        |
| DELETE | `/expenses/{expense_id}`           | Delete expense                      |

## Example shapes

```json
// User
{ "id": "uuid", "email": "a@example.com", "name": "Alex", "created_at": "2026-10-19T14:00:00Z" }

// Expense
{
  "id": "uuid",
  "household_id": "uuid",
  "description": "Electricity — October",
  "amount_cents": 12000,
  "currency": "USD",
  "paid_by": "user-uuid",
  "splits": [
    { "user_id": "uuid", "amount_cents": 6000 },
    { "user_id": "uuid", "amount_cents": 6000 }
  ],
  "created_at": "2026-10-19T14:00:00Z"
}
```
