# API Contract (v1)

Base URL: `/api/v1`. The live, authoritative spec is served by the backend at `/docs` (Swagger)
and `/openapi.json`. This file is the human-readable plan both clients build against.

Status: **draft** — endpoints below are planned, not yet implemented.

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
| POST   | `/households/{id}/invite`             | Generate invite code         |
| POST   | `/households/join`                    | Join with invite code        |
| DELETE | `/households/{id}/members/{user_id}`  | Remove member / leave        |

## Chores

| Method | Path                               | Description            |
| ------ | ---------------------------------- | ---------------------- |
| GET    | `/households/{id}/chores`          | List chores            |
| POST   | `/households/{id}/chores`          | Create chore           |
| PATCH  | `/chores/{chore_id}`               | Update / reassign      |
| POST   | `/chores/{chore_id}/complete`      | Mark complete          |
| DELETE | `/chores/{chore_id}`               | Delete chore           |

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
