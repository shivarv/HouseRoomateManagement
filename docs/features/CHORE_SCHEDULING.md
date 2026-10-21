# Feature: Chore Scheduling, Open Chores, Activity & Monthly Report

Status: **in progress** · builds on [CHORE_ROTATION.md](CHORE_ROTATION.md)

## Decisions

| Topic | Decision |
| ----- | -------- |
| Several times a day | Not a feature. Create separate chores, e.g. "Cooking – Lunch" and "Cooking – Dinner". The automatic stagger gives them different people. |
| Weekly chores | Once per week, done on **any day** of that week (Mon–Sun in the household's timezone). |
| Who can mark things done | **Anyone** in the house, for themselves or on behalf of someone else. Undo is allowed. Every change is recorded. |
| Activity | Every update goes into an activity feed that **everyone** in the house can see. |
| Report | The **current month** dashboard is visible to everyone. **Past months** are only visible to admins, in a History view. |

## 1. Chore settings

| Setting | Values | Meaning |
| ------- | ------ | ------- |
| `frequency` | `daily` · `weekly` | How often the chore comes up: every day, or once per Mon–Sun week. |
| `assignment_mode` | `rotation` · `open` | **rotation**: round-robin, the app says whose turn it is. **open**: nobody is assigned; whoever does it logs it. |
| `target_per_week` | number, optional (open chores only) | Only used for display, e.g. "2 of 4 this week". |

Existing chores become `daily` + `rotation`.

## 2. Rotation chores (daily or weekly)

The rotation formula from CHORE_ROTATION.md now counts **periods** (days or weeks) instead of days:

```
period_start(d) = d                      (daily)
                = Monday of d's week     (weekly)
step            = 1 day (daily) or 7 days (weekly)
assignee(d)     = order[ ((period_start(d) - rotation_start).days / step) mod N ]
```

The stagger and the "today's person keeps today" rule work the same way, per period.

### Who actually did it

Each task stores two people:
- **`member_id`**: whose turn it was.
- **`completed_by_id`**: who actually did it.

If Cy does Bea's cooking, the task is done and the record says *Cy covered for Bea*. The rotation doesn't shift.

### Missed days are filled in

When anyone opens the app, the backend fills in any periods since the chore's last task, up to 31 days back. That makes days when nobody opened the app show up honestly as **missed** in the report.

A chore that is paused and later resumed starts tracking again from the day it was resumed (`tracked_from`), so the paused days don't count as missed.

## 3. Open chores (e.g. Dispose garbage, which is open by default)

- They aren't in the schedule and aren't assigned to anyone.
- The card shows **one button per person**, labelled with how many times they did it **this year**,
  and ordered by fewest this year, then fewest this month, then whoever did it longest ago. Any
  remaining tie is broken randomly, but stays fixed for the day.
- Whoever did it taps their own name. A chore can be logged several times a day.
- The first person in that order is shown as **"Suggested next"**. It's a hint, not an assignment
  (`services/suggest.py`).
- The card also shows who did it last and when, and how many times this week (against the target, if set).
- Each log can be removed again (undo), and the removal is recorded too.

## 4. Activity feed (everyone)

Every change is saved as an event and shown newest first:

| Event | Example |
| ----- | ------- |
| completed | "Cy did Cooking · Bea's turn" / "Ann marked Clean hall done for Dev" |
| reopened | "Ann undid Cooking (Mon, Oct 20)" |
| logged / log_removed | "Gus took out Dispose garbage" |
| chore_created / chore_updated / rotation_changed | "Ann changed the order of Cooking" |
| member_added / member_removed | "Ann added Hal" |

Events keep the chore's name, so they still make sense after the chore is deleted.

## 5. Monthly report

`GET /households/{id}/report?month=YYYY-MM`. Without `month` it returns the current month, which
everyone can see; other months are admin only.

For each chore, one row per person, **sorted by how many times they did it**:

| Column | Rotation chores | Open chores |
| ------ | --------------- | ----------- |
| Done | own turns done + turns covered for others | times logged |
| Share | done ÷ total done for this chore | same |
| Turns | turns assigned so far this month | — |
| Missed | own turns that ended without being done | — |
| Covered by others | own turns someone else did | — |
| Last done | — | date |

A **leaderboard** across all chores shows each person's total done and total missed. "Fair share" is
1 ÷ the number of active people. The UI highlights anyone at 0 or well below their fair share.

`GET /households/{id}/report/months` (admin) lists the months that have data, for the History view.

## API changes

| Method | Path | Change |
| ------ | ---- | ------ |
| POST/PATCH | `/households/{id}/chores`, `/chores/{id}` | + `frequency`, `assignment_mode`, `target_per_week` |
| POST | `/tasks/{id}/complete` | body `{ completed_by_member_id? }`, defaults to me; anyone in the house can call it |
| POST | `/tasks/{id}/reopen` | anyone in the house |
| POST | `/chores/{id}/logs` | open chores: `{ member_id? }`, defaults to me |
| DELETE | `/chore-logs/{id}` | undo a log |
| GET | `/households/{id}/activity?limit=&before=` | activity feed |
| GET | `/households/{id}/report?month=` | monthly report |
| GET | `/households/{id}/report/months` | admin: months available |
| GET | `/households/{id}/tasks/today`, `/me/tasks/today` | + weekly tasks for this week, + `open` chores |

## Data model (migration 0002)

```
chores            + assignment_mode text default 'rotation'
                  + target_per_week int NULL
                  + tracked_from    date        -- backfill never goes earlier than this
                  frequency now 'daily' | 'weekly'
chore_tasks       + completed_by_id uuid FK → household_members NULL
                  due_date = period start (the day, or Monday for weekly)
chore_logs        id, chore_id, member_id (who did it), logged_by_id, done_on date, created_at
activity_events   id, household_id, actor_id, action, chore_id NULL, chore_name, subject_id NULL,
                  assignee_id NULL, due_date NULL, detail NULL, created_at
```

Existing tasks that are done get `completed_by_id = member_id`.
