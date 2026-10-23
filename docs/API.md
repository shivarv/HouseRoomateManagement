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
| GET    | `/auth/me`       | Yes  | Current user, incl. `last_household_id` (house the apps open on) |
| PUT    | `/auth/me/last-household` | Yes | `{ household_id }` — remember the house I switched to (404 if not a member). Also set automatically on create / join |

## Households

| Method | Path                                  | Description                  |
| ------ | ------------------------------------- | ---------------------------- |
| GET    | `/households`                         | Households I belong to       |
| POST   | `/households`                         | Create household: `{ name, address, timezone? }`. `address` required. 409 if I already created a house with that name (case-insensitive; other people's houses don't count) |
| GET    | `/households/{id}`                    | Household detail + members   |
| PATCH  | `/households/{id}`                    | Change name / address / timezone (admin). Renaming follows the same per-creator uniqueness |
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
| GET    | `/households/{id}/shopping`            | `{ needed, recently_bought (14 days), categories (the house's sections, in order), quick_add (the admin's quick-add items: name + type, alphabetical) }` |
| POST   | `/households/{id}/shopping`            | Add `{ name, quantity?, category?, note? }` → 201, or 200 with the existing item if it's already on the list. `category` is a category `key` of the house (400 if unknown); left out, it comes from the matching quick-add item, else a guess from the name, else `other` |
| POST   | `/households/{id}/shopping/bought`     | One trip: `{ item_ids }`. Items someone else already bought keep their buyer |
| PATCH  | `/shopping/{id}`                       | Edit `{ name?, quantity?, category?, note? }` — still-needed items only (409) |
| POST   | `/shopping/{id}/bought`                | Mark one item bought                                                        |
| POST   | `/shopping/{id}/undo`                  | Back on the list — the buyer or whoever added it                            |
| DELETE | `/shopping/{id}`                       | Take a still-needed item off the list — anyone                              |

Activity feed actions: `shopping_added`, `shopping_bought`, `shopping_unbought`, `shopping_removed`.

### Grocery settings (admin only)

Every house starts with the standard categories (groceries, toiletries, cleaning, household, other) and 15 quick-add items. `other` is the fallback and can't be deleted.

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET    | `/households/{id}/grocery-settings`          | `{ categories, presets, suggestions }`. Suggestions: names added in the last 120 days that aren't quick-add items or dismissed, `{ name, times_added, category_key }`, most added first |
| POST   | `/households/{id}/grocery-settings/restore`  | Bring back removed standard categories and quick-add items; custom ones are untouched |
| POST   | `/households/{id}/grocery-categories`        | `{ label, icon? }` → 201. Labels are unique per house (409) |
| PATCH  | `/grocery-categories/{id}`                   | `{ label?, icon? }`. The `key` never changes |
| DELETE | `/grocery-categories/{id}`                   | Its items and quick-add items move to `other` (400 for `other` itself) |
| PUT    | `/households/{id}/grocery-categories/order`  | `{ ids }`: every category of the house, in the new order |
| POST   | `/households/{id}/grocery-presets`           | `{ name, category_key? }` → 201. Also how a suggestion is accepted. 409 if already a quick-add item |
| PATCH  | `/grocery-presets/{id}`                      | `{ name?, category_key? }` |
| DELETE | `/grocery-presets/{id}`                      | Removes it from quick add (kept as dismissed, so it isn't suggested again) |
| POST   | `/households/{id}/grocery-suggestions/dismiss` | `{ name }`: stop suggesting it |

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

## Reminders (bills)

Recurring house payments. Admins set them up; everyone sees them and marks them paid. Every house starts with Rent (everyone pays, fixed), Electricity (anyone, changes each time), WiFi (anyone, fixed) and Gas (anyone, changes each time), all monthly and due on the 1st.

- `frequency`: `monthly` | `weekly` | `daily`. Each occurrence (*period*) starts on the 1st, on Monday, or on the day, and shows up as a reminder then.
- `due_day`: monthly → day of the month (29–31 use the last day of short months); weekly → weekday, 1 = Monday … 7 = Sunday; daily → unused.
- `amount_type`: `fixed` (the bill's `amount_cents` repeats every period) or `variable` (an admin sets each period's amount, e.g. when the electricity bill arrives; `last_amount_cents` is a hint). Money is integer cents + a 3-letter currency, display only.
- `payer_mode`: `one` (a named `payer_id`; anyone can still mark it for them), `anyone` (first payer settles it; later clicks get 409 "Bea already paid it"), `everyone` (each person pays their share and is counted: `paid_count` of `expected_count` active people; `share_cents` = amount ÷ people).
- `status` of a period: `paid`, `due` (today or within 3 days), `overdue`, `upcoming`.

| Method | Path | Who | Description |
| ------ | ---- | --- | ----------- |
| GET    | `/households/{id}/bills?include_paused=` | member | `{ today, bills }`: each bill with its `current` period (payments, amount, status). `include_paused` only works for admins |
| GET    | `/bills/{id}/history?limit=6` | member | The periods before the current one, newest first (max 24) |
| POST   | `/households/{id}/bills` | admin | `{ name, icon?, payer_mode?, payer_id?, frequency?, due_day?, amount_type?, amount_cents?, currency?, note? }` → 201 |
| PATCH  | `/bills/{id}` | admin | Any of the above, plus `is_active` (pause/resume). `amount_cents: null` and `note: ""` clear them |
| DELETE | `/bills/{id}` | admin | Deletes the bill and its history (pause it to keep the history) |
| PUT    | `/bills/{id}/amount` | admin | Variable bills: `{ amount_cents, period? }` (any date in the period; default the current one; `null` clears). Fixed bills → 400 |
| POST   | `/bills/{id}/pay` | member | `{ member_id?, period? }`: me and the current period by default. Future periods → 400; already paid → 409 |
| DELETE | `/bill-payments/{id}` | member | Undo: whoever paid, whoever marked it, or an admin |

Activity feed actions: `bill_paid`, `bill_unpaid`, `bill_amount_set`, `bill_created`, `bill_updated`, `bill_deleted`.
