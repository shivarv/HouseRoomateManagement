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

## Swaps ("Ask for a swap")

See [features/CHORE_TRANSFER.md](features/CHORE_TRANSFER.md). Any member can ask; the first person to accept wins.

| Method | Path                               | Description                                                                 |
| ------ | ---------------------------------- | --------------------------------------------------------------------------- |
| POST   | `/chores/{chore_id}/swaps`         | Ask the house to take my turn. Body `{ due_date, note? }`. Asking again returns the same request |
| GET    | `/households/{id}/swaps`           | Open requests, each with `can_accept` and `payback_preview` for the caller |
| GET    | `/me/swaps`                        | Open requests in all my households                                          |
| POST   | `/swaps/{swap_id}/accept`          | Take the turn. **409** if someone else already took it, or it is no longer open. Same person again → 200 |
| POST   | `/swaps/{swap_id}/cancel`          | Requester (open), or either person (accepted, before the turn is done)      |

`TaskOut` has `swap: { id, role: "given" | "payback", other, can_cancel } | null` and `swap_request_id`.
Schedule slots have `swapped_with`.

## Help requests (🔔 Notifications)

Anyone can ask their house for a hand; anyone in the house can mark it done. The first person to mark it done wins (**409** "Bea already marked it done" for everyone after; the same person again → 200).

| Method | Path                                   | Description                                                                 |
| ------ | -------------------------------------- | --------------------------------------------------------------------------- |
| GET    | `/me/help-requests`                    | Open requests in all my households, ones done in the last 14 days, and all of mine. Each has `is_mine`, `can_reopen` |
| POST   | `/households/{id}/help-requests`       | Ask for help. Body `{ title, details? }` (`title`: a preset or free text, ≤120) |
| PATCH  | `/help-requests/{id}`                  | Edit `{ title?, details? }`. Requester only (403), open only (409)          |
| POST   | `/help-requests/{id}/done`             | Mark done — anyone in the house                                             |
| POST   | `/help-requests/{id}/reopen`           | Undo "done" — the requester or whoever marked it done                       |
| DELETE | `/help-requests/{id}`                  | Withdraw — requester only, open only                                        |

Activity feed actions: `help_requested`, `help_updated`, `help_done`, `help_reopened`, `help_withdrawn`.

## Shopping list (🛒 Groceries)

Things the house needs to buy. No prices. Categories (`groceries`, `toiletries`, `cleaning`, `household`, `other`) are guessed from the name when not given. A name already on the list (any capitalisation) is never added twice. The first person to mark an item bought wins (**409** "Bea already bought it").

| Method | Path                                   | Description                                                                 |
| ------ | -------------------------------------- | --------------------------------------------------------------------------- |
| GET    | `/households/{id}/shopping`            | `{ needed, recently_bought (14 days), suggestions (bought before, not on the list) }` |
| POST   | `/households/{id}/shopping`            | Add `{ name, quantity?, category?, note? }` → 201, or 200 with the existing item if it's already on the list |
| POST   | `/households/{id}/shopping/bought`     | One trip: `{ item_ids }`. Items someone else already bought keep their buyer |
| PATCH  | `/shopping/{id}`                       | Edit `{ name?, quantity?, category?, note? }` — still-needed items only (409) |
| POST   | `/shopping/{id}/bought`                | Mark one item bought                                                        |
| POST   | `/shopping/{id}/undo`                  | Back on the list — the buyer or whoever added it                            |
| DELETE | `/shopping/{id}`                       | Take a still-needed item off the list — anyone                              |

Activity feed actions: `shopping_added`, `shopping_bought`, `shopping_unbought`, `shopping_removed`.

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
