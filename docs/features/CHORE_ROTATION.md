# Feature: Chore Rotation & Today's Tasks

Status: **implemented** (backend, web, iOS)

## Goal

1. A household admin configures, from web or iOS:
   - the **people** living in the house (e.g. 8 roommates)
   - the **chores** (initially: Cooking, Clean hall, Dispose garbage)
   - the **rotation order** of people for each chore
2. The configuration is saved in PostgreSQL and survives restarts / reinstalls.
3. Each chore is assigned **round-robin**, one person per day, cycling through the order and
   repeating forever (person 1 → 2 → … → 8 → 1 → …).
4. When a person logs in, the app shows **"Your tasks for today"** as the reminder, and they can
   mark a task done.

## Example

8 roommates: A B C D E F G H. Three daily chores, each with its own starting offset so one
person doesn't get all three on the same day:

| Date   | Cooking | Clean hall | Dispose garbage |
| ------ | ------- | ---------- | --------------- |
| Day 1  | A       | B          | C               |
| Day 2  | B       | C          | D               |
| Day 3  | C       | D          | E               |
| …      | …       | …          | …               |
| Day 8  | H       | A          | B               |
| Day 9  | A       | B          | C  ← cycle repeats |

When **A** logs in on Day 1, they see: *Today: Cooking*.
When **C** logs in on Day 1, they see: *Today: Dispose garbage*.

## Core rule (how the assignee is decided)

The rotation is **calendar-based and deterministic**: given a chore's ordered member list `M`
(length `N`) and its `rotation_start_date` `S`, the assignee for date `D` is:

```
assignee(D) = M[ (D - S).days mod N ]
```

- No background job is needed to "advance" the rotation, and every client gets the same answer.
- "Today" is calculated in the **household's timezone** (stored on the household), not in UTC
  or the device's timezone.
- **Staggering:** a new chore defaults to `rotation_start_date = today - k`, where `k` is the
  number of chores the household already has. That's what produces the shifted table above.
  The admin can still change the order for each chore.

### Changing the rotation (someone joins, leaves, or the order changes)

- New people are added to the **end** of every chore's rotation; removed people are taken out of all of them.
- **During setup** (the chore has no tasks before today yet) the start date is kept, so the stagger
  between chores survives while you add your roommates one by one.
- **Once a rotation is in use**, the start date is rebased so **today's person keeps today** and the
  order continues from them. If today's person was removed, the next person (in the old order) who is
  still there takes today.
- Past tasks are never rewritten. A *pending* task for today follows the current rotation; a *done*
  task is never changed.

## Data model (PostgreSQL)

```
households
  id                uuid PK
  name              text
  timezone          text            -- e.g. "America/New_York"
  created_at, updated_at

household_members
  id                uuid PK
  household_id      uuid FK → households
  display_name      text            -- "Alex"; can be set before the person has an account
  user_id           uuid FK → users NULL   -- linked when the roommate signs up / accepts invite
  role              text            -- 'admin' | 'member'
  is_active         boolean
  created_at, updated_at
  UNIQUE (household_id, user_id)

chores
  id                  uuid PK
  household_id        uuid FK → households
  name                text            -- "Cooking"
  position            int             -- display order
  frequency           text            -- 'daily' (only value for now)
  rotation_start_date date
  is_active           boolean
  created_at, updated_at

chore_rotation_members           -- ordered rotation for a chore
  chore_id          uuid FK → chores
  member_id         uuid FK → household_members
  position          int             -- 0..N-1
  PRIMARY KEY (chore_id, position)
  UNIQUE (chore_id, member_id)

chore_tasks                      -- one row per chore per day; the saved record of who had it
  id                uuid PK
  chore_id          uuid FK → chores
  member_id         uuid FK → household_members
  due_date          date
  status            text            -- 'pending' | 'done'
  completed_at      timestamptz NULL
  created_at, updated_at
  UNIQUE (chore_id, due_date)
```

### Why both a formula and a `chore_tasks` table?

- The **formula** decides who gets a chore, so there's no cron job and nothing gets out of sync.
- **`chore_tasks`** stores what actually happened, so "done" has somewhere to live and history
  still holds after the rotation changes.
- Tasks are generated **on demand**: when anyone opens today's tasks, the chore list or the schedule,
  the backend inserts today's row for each chore with
  `INSERT … ON CONFLICT (chore_id, due_date) DO NOTHING`, so requests that run at the same time are
  safe. Days when nobody opened the app aren't filled in later, and future days are calculated
  without being stored.
- "Missed earlier" (overdue) = my tasks from the last 7 days that are still pending.

## API (additions to [API.md](../API.md))

| Method | Path                                       | Who    | Description                                         |
| ------ | ------------------------------------------ | ------ | --------------------------------------------------- |
| GET    | `/households/{id}/members`                 | member | List people in the house                            |
| POST   | `/households/{id}/members`                 | admin  | Add a person `{ display_name }`                     |
| PATCH  | `/members/{member_id}`                     | admin  | Rename / deactivate                                 |
| GET    | `/households/{id}/chores`                  | member | Chores with their rotation order                    |
| POST   | `/households/{id}/chores`                  | admin  | `{ name, frequency, member_ids: [ordered] }`        |
| PUT    | `/chores/{chore_id}/rotation`              | admin  | Replace order `{ member_ids: [ordered] }`           |
| GET    | `/households/{id}/schedule?from=&to=`      | member | Calendar preview: who has which chore on each day (max 31 days) |
| GET    | `/me/tasks/today`                          | member | **The reminder:** my tasks for today                |
| GET    | `/households/{id}/tasks/today`             | member | Everyone's tasks for today                          |
| POST   | `/tasks/{task_id}/complete`                | member | Mark done (only the assignee or an admin)           |

`GET /me/tasks/today` response:

```json
{
  "date": "2026-10-19",
  "tasks": [
    {
      "id": "uuid",
      "chore": { "id": "uuid", "name": "Cooking" },
      "due_date": "2026-10-19",
      "status": "pending",
      "next_assignee": { "id": "uuid", "display_name": "Bea" }
    }
  ]
}
```

## Default chores

When a household is created, the backend adds the three default chores (**Cooking**,
**Clean hall**, **Dispose garbage**), each staggered as described above. Each one gets its
rotation order once members are added. The admin can rename, deactivate or add chores later.

## Screens (web + iOS, same flow)

| Screen            | Content                                                                    |
| ----------------- | -------------------------------------------------------------------------- |
| **Setup: People** | Add / remove roommates by name; invite to link an account                  |
| **Setup: Chores** | List of chores; tap a chore → drag to reorder its rotation                 |
| **Today** (home)  | Banner/card: "Your tasks today: Cooking" + **Mark done**; below it, who has each chore today |
| **Schedule**      | 7-day grid (dates × chores) built from `/schedule`                         |

The **Today** screen is the first screen after login, and it is the in-app reminder.

## Reminders: phased

1. **v1 (this design):** in-app. The Today screen and a badge for pending tasks.
2. **v2:** an iOS local notification each morning at a time the user picks, scheduled from the
   upcoming `/schedule` data, so no push server is needed.
3. **v3:** server push (APNs / Web Push) from a daily backend job, if reminders must arrive
   even when the app hasn't been opened.

## Assumptions (current behavior)

1. **Accounts:** the admin adds people by name, and each person can link an account later. Only
   people with an account can log in and see "my tasks".
2. **Missed days:** the rotation follows the calendar. If A skips cooking on Day 1, B still cooks
   on Day 2 and A's task stays `pending` (shown as overdue). The rotation never waits for anyone.
3. **One person per chore per day.** Pairs (e.g. 2 people cleaning) aren't supported yet.
4. **Daily only.** Weekly chores (e.g. one person per week) would be added later as a `frequency`
   value that uses weeks instead of days in the formula.
