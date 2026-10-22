# Feature: Turn Transfers (swap a turn, pay it back)

Status: **implemented** (backend, web, iOS) · builds on [CHORE_ROTATION.md](CHORE_ROTATION.md) and [CHORE_SCHEDULING.md](CHORE_SCHEDULING.md)

> **Implementation names.** The code calls these *swaps* everywhere: table `chore_swaps`, model
> `ChoreSwap`, service [swaps.py](../../backend/app/services/swaps.py), routes under `/swaps`, activity
> actions `swap_*`. "Transfer" below means the same thing.

## The idea

Sometimes I can't do my turn. I post a **transfer request** to the whole house. The first
person who says **yes** takes my turn, and in return **I take their next turn of the same
chore**. It is a swap, so nobody ends up doing more work than the rotation says.

This is different from what exists today:

| Today's buttons | Transfer |
| --------------- | -------- |
| "I did it" / "It's done" / "Someone else did it" record **who did it after the fact**. Nothing is paid back. | Agreed **before** the turn. Changes **who is on duty**. Paid back automatically. |

Both stay. Covering without a payback is still allowed.

## Decisions

| Topic | Decision (proposed) |
| ----- | ------------------- |
| Who is asked | Everyone eligible. It is a broadcast, not a request to one person. |
| Who is eligible | Active members who have an account, are **in that chore's rotation**, and are not the requester. People added by name who haven't joined can't accept, because they can't log in. |
| Who wins | The **first** person to accept. Everyone after that gets "Already taken by Bea". |
| Payback | **Decided:** the requester takes the acceptor's **next turn of the same chore** after the transferred turn. A daily turn is paid back with a daily turn, and a weekly turn with a weekly one. |
| Naming | **Decided:** the action is called **"Ask for a swap"** in the UI. |
| Which turns can be transferred | My own pending turns: the current one or a future one up to the schedule window (31 days). Done turns and past turns can't be transferred. |
| Swapping again | **Allowed.** A turn can be swapped again later. For example, Bea took Shiva's Tue 21 and can later ask for a swap on it herself. The only limit is **one open request per turn at a time**. It is checked in code at the moment of asking, not by a database rule. |
| Expiry | An open request expires when its turn's period ends: end of the day for daily chores, Sunday for weekly ones. |
| Cancel | The requester can cancel while the request is open. After it is accepted, **either side** can cancel until the transferred turn is done. Both turns then go back to who had them before the swap. A swap can only be cancelled while it is the **latest** swap on its two turns. If one of them was swapped onward, that later swap has to be cancelled first. |
| History | Every step (requested, accepted, cancelled, expired) goes in the activity feed. |
| Missed turns | A payback is a normal turn. If the requester skips it, it shows as **missed** for them, like any other turn. |

## 1. Data model

One new table. The swaps are read from it; no separate "overrides" table is needed.

```
chore_swaps
  id              uuid PK
  household_id    FK households      (for listing)
  chore_id        FK chores
  given_date      date               turn being given away (period start)
  requester_id    FK household_members   whose turn it was
  acceptor_id     FK household_members   NULL until accepted
  payback_date    date               NULL until accepted; acceptor's next turn, now the requester's
  status          open | accepted | cancelled | expired
  note            varchar(200)       optional "can't, travelling"
  created_at, resolved_at
```

Indexes (for speed only, no uniqueness rules, so a turn can be swapped any number of times over its life):
- `(household_id, status)` for the "open requests" list.
- `(chore_id, given_date)` and `(chore_id, payback_date)` for working out who is on duty.

Migration: a new Alembic revision `…_0003_chore_swaps.py`.

## 2. Who is on duty (the core change)

Today, who is on duty comes from the formula alone. `ensure_chore` even **resets** the
current pending turn back to the formula person ([tasks.py:79-90](../../backend/app/services/tasks.py#L79-L90)).
A transfer would be wiped out on the next page load unless every lookup checks transfers first.

Add one helper and use it everywhere the formula is used now:

```python
def on_duty(chore, day, swaps) -> member_id:
    """Rotation formula, then accepted swaps on top. The latest swap on a date wins."""
    if (t := swaps.latest.get(day)):
        return t.acceptor_id if t.given_date == day else t.requester_id
    return rotation.assignee(order, chore.rotation_start_date, day, step)
```

`swaps` is loaded once per chore: the accepted swaps in the date range. `latest[day]` is the most
recently accepted one (by `resolved_at`) whose `given_date` or `payback_date` is that day. Because
the latest one wins, a turn can be swapped again and again, and each swap builds on the one before.
`rotation.py` stays pure.

Call sites to switch over:

| Where | What it does |
| ----- | ------------ |
| `ensure_chore`, back-fill loop ([tasks.py:77](../../backend/app/services/tasks.py#L77)) | past turns |
| `ensure_chore`, current turn ([tasks.py:81](../../backend/app/services/tasks.py#L81)) | today's / this week's turn |
| `upcoming_for` ([tasks.py:345](../../backend/app/services/tasks.py#L345)) | "your next turns" on My Day. `rotation.next_turn` ignores swaps, so step through periods with `on_duty` (bounded by N periods). |
| `task_out` → `next_assignee` ([tasks.py:384](../../backend/app/services/tasks.py#L384)) | "Next: Cy" |
| `schedule` ([tasks.py:438](../../backend/app/services/tasks.py#L438)) | Schedule tab |

Accepting or cancelling a transfer must also update the already-saved `chore_tasks` row for
any of the two dates that has one (the current period). Run `ensure_chore` for that chore in
the same transaction.

### Many people pick the same request

Several people can press **"I'll take it"** at the same moment. **Exactly one wins, and the
database decides, not the browser.** Clicks are first come, first served in the order the
database commits them.

> **Rule: the first "yes" is final.** Once a request is accepted, no later click can change who
> took it, even one sent a millisecond later. A later click writes nothing and gets told who
> already took it. The only way to undo an accepted swap is an explicit **Cancel swap** by one
> of the two people in it.

**Backend: one transaction per accept**

```python
def accept(db, transfer_id, me):
    # 1. Lock the request row. Concurrent accepts of the SAME request wait here, one at a time.
    t = db.execute(select(ChoreSwap).where(ChoreSwap.id == transfer_id)
                   .with_for_update()).scalar_one_or_none()
    if t is None:                      raise NotFound("Swap request not found")
    if t.status == "accepted" and t.acceptor_id == me.id:
        return t                       # my own double-click / retry: same answer, no error
    if t.status == "accepted":         raise Conflict(f"{t.acceptor.display_name} already took it")
    if t.status in ("cancelled", "expired"):
                                       raise Conflict("This swap request is no longer open")
    if not eligible(t, me):            raise BadRequest("You can't take this swap")

    # 2. Lock the chore row too, so two DIFFERENT requests for the same chore can't both pick
    #    the same payback turn (e.g. Bea accepts two requests at once and both choose her Fri 24).
    db.execute(select(Chore.id).where(Chore.id == t.chore_id).with_for_update())

    if on_duty(chore, t.given_date) != t.requester_id:   # turn changed hands since asking
                                       raise Conflict("This swap request is no longer open")
    payback = first date after t.given_date where on_duty(chore, date) == me
    if payback is None:                raise BadRequest("You have no upcoming turn to give back")

    t.status, t.acceptor_id, t.payback_date, t.resolved_at = "accepted", me.id, payback, now
    activity.record(db, ..., "swap_accepted", me, subject_id=t.requester_id, ...)
    ensure_chore(db, chore, today)     # update the saved current turn if it is one of the dates
    db.commit()
```

- The first accept gets the row lock and commits. Everyone queued behind it then reads
  `status = accepted` and gets **409**.
- The same person clicking twice (or the browser retrying) gets **200** with the same result, not
  an error.
- Accepting a cancelled or expired request gets **409** "no longer open".

**No database rules, just locks at the moment of the click.** The database doesn't forbid a turn
being swapped twice; it may be, later on. The locks only make sure that clicks arriving
**at the same moment** are handled one after another, never mixed together:

- **Accept vs. accept** (same request): the request row lock. The first one wins.
- **Accept vs. cancel** (same request): the same lock. Whichever commits first wins, and the other
  gets **409** with the current state.
- **Two accepts on different requests of the same chore** (e.g. Bea takes two at once): the chore
  row lock, so the second one sees the first one's result when choosing Bea's payback turn.
- **Two "Ask for a swap" clicks on the same turn** (double-click, or Shiva on two devices):
  `request()` also locks the chore row and checks "no open request for this turn yet". The second
  click gets **200** with the existing request instead of creating a duplicate.

Locks last only until the transaction commits, a few milliseconds. Nobody waits in a way they would notice.

**Errors the API returns**

| Case | Status | Message shown |
| ---- | ------ | ------------- |
| Someone else accepted first | 409 | "Bea already took it" |
| Cancelled or expired meanwhile | 409 | "This swap request is no longer open" |
| Requester tries to accept own request | 400 | "You can't take your own swap" |
| Not in that chore's rotation | 400 | "You can't take this swap" |
| No upcoming turn to give back | 400 | "You have no upcoming turn to give back" |
| Turn changed hands since the request was made | 409 | "This swap request is no longer open" |
| Same person accepts again | 200 | (no message; same result) |

**Web: what the user sees**
- When pressed, **"I'll take it"** shows a spinner and is disabled, so one person can't send a burst of clicks.
- **200:** the strip turns green: "You took Shiva's Cooking (Tue 21). Shiva does your Fri 24."
- **409:** the strip turns grey and shows the server's message ("Bea already took it").
  The swap list, tasks and schedule refetch, so the strip disappears for good.
- **Network error:** keep the button active with "Couldn't reach the server, try again". Retrying is
  safe because a repeat accept by the same person returns 200.
- Other people's screens catch up on window focus and on the 5-minute refetch. A stale strip
  just gives them the 409 message if they press it.

### Rotation and membership changes

- **Rotation reordered:** accepted transfers keep their dates, so both swapped turns stay
  where they are. Everything else follows the new order.
- **Requester or acceptor removed from the house or the rotation:** cancel their open or
  accepted transfers that haven't been done yet, and log it as `swap_cancelled`
  ("automatically, member removed").
- **Chore deleted or paused:** cancel its live transfers.

## 3. API

| Method | Path | Who | Notes |
| ------ | ---- | --- | ----- |
| `POST` | `/chores/{chore_id}/swaps` | turn owner | body `{ due_date, note? }`. 400 if it isn't my pending turn or it already has a transfer. |
| `GET` | `/households/{id}/swaps` | members | Each item includes `can_accept` and `payback_preview` (the date *I* would give back) for the logged-in user. |
| `GET` | `/me/swaps` | me | My open requests and my accepted ones (both sides), for badges on My Day. |
| `POST` | `/swaps/{id}/accept` | eligible member | 409 if taken or expired |
| `POST` | `/swaps/{id}/cancel` | requester (open); requester or acceptor (accepted, before done) | |

`TaskOut` gains `swap: { id, role: "given" \| "payback", other, can_cancel } | null` and `swap_request_id` so the
card can show its badge without another request. Update [docs/API.md](../API.md).

Expire lazily: mark `open` requests whose period has ended as `expired` during `sync()`. Then
no cron job is needed.

## 4. Activity history

New `action` values, all written by `activity.record` in the same transaction:

| action | actor | subject | Shown as |
| ------ | ----- | ------- | -------- |
| `swap_requested` | requester | — | 🔁 **Shiva** asked for someone to take **Cooking** for Tue 21 |
| `swap_accepted` | acceptor | requester | 🤝 **Bea** took **Shiva**'s **Cooking** (Tue 21). Shiva takes Bea's turn on Fri 24 |
| `swap_cancelled` | whoever cancelled | other party | ↩️ **Shiva** cancelled the swap with **Bea** for **Cooking** |
| `swap_expired` | — | requester | ⌛ Nobody took **Shiva**'s **Cooking** (Tue 21) |

Store the payback date in `detail` (or add a second date column) so the sentence still makes
sense after the transfer row changes. Add a `"swap"` kind to
[activityText.ts](../../web/src/features/chores/activityText.ts) and a matching filter chip in the
Activity tab. Mirror it in iOS `ActivityText.swift`.

The completion entries themselves don't change. When Bea does the transferred turn, she is
now its assignee, so it reads "Bea did Cooking" with no "Shiva's turn" suffix.

## 5. UI

### Asking (requester)

- On **my** pending turn card, add **"Ask for a swap"** as an item in the ▾ menu. Don't add a
  fourth button; the card already has three actions.
- Also put it on my slots in the **Schedule** tab (click my future slot, then "Ask for a swap"), so
  people can plan ahead.
- A small confirm sheet:
  > **Swap Cooking · Tue 21?**
  > Whoever accepts takes this turn. You'll do their next Cooking turn in return.
  > [ optional note ]  **[Send to the house]**
- After sending, the card shows an amber badge **"Swap requested · waiting"** with a
  **Cancel request** link.

### Answering (everyone else)

- A **"Swap requests"** strip at the top of **Today** and **My Day**. It only shows when there are
  requests I can accept:
  > 🔁 **Shiva** needs someone for **Cooking** · Tue 21 — "travelling"
  > You'd give back your Cooking turn on **Fri 24**.  **[I'll take it]**  [Not me]
- Showing the payback date per person (`payback_preview`) is the key detail: people agree to a
  specific trade, not a vague one.
- **"Not me"** only hides it for this user (localStorage). Nothing is sent to the server, and
  others still see it.
- When someone accepts, their strip changes to a confirmation. Everyone else's strip disappears on
  the next refetch. If two people click at once, the loser sees a toast: "Bea already took it".

### After a swap

- Transferred turn card (Bea's now): an indigo badge **"⇄ from Shiva"**.
- Payback turn card (Shiva's now): a badge **"⇄ paying back Bea"**.
- Schedule tab: a small ⇄ icon on both swapped slots, with a tooltip naming the other person.
- Either side sees **Cancel swap** in the ▾ menu until the transferred turn is done.

### Keeping it fresh

There are no push notifications yet. Use the existing query settings (`refetchOnWindowFocus`,
5-minute `refetchInterval` in [hooks.ts:15](../../web/src/features/chores/hooks.ts#L15)) for the
requests list. Invalidate tasks, schedule, activity and transfers after accept or cancel, as
`useInvalidateChoreData` already does. Push or email ("Shiva needs a swap") can come later.

## 6. Build order

1. Migration + `ChoreSwap` model.
2. `on_duty` helper; switch the five call sites over. With no transfers, behaviour is
   unchanged, so the existing tests should still pass.
3. Service functions: `request`, `accept` (race-safe), `cancel`, lazy `expire`. Activity events.
4. Routes and schemas, `TaskOut.transfer`, API.md.
5. Web: hooks + API client, the ▾ menu item and confirm sheet, the requests strip, badges, the
   Schedule ⇄ icon, activity text.
6. iOS mirror.

## 7. Tests

- Swap shows in schedule and `/me/tasks/today` for both people, and `next_assignee` respects it.
- `ensure_chore` doesn't overwrite a swapped current turn.
- Two accepts at once (run them in two threads with separate DB sessions): exactly one 200,
  one 409 "already took it", and one `swap_accepted` event.
- Same person accepts twice: both 200, one event.
- Accept vs. cancel at the same time: exactly one wins.
- One person accepts two requests for the same chore at once: they get different payback turns.
- Can't ask: a done turn, someone else's turn. A second ask on a turn with an open request
  returns the existing one.
- Swapping again works: Shiva → Bea, then Bea → Cy on the same turn. Cy is on duty, and both
  paybacks are in place.
- Cancelling an older swap whose turn was swapped onward is refused until the later one is cancelled.
- Can't accept: requester, a member not in the rotation, an expired request.
- Cancel before done brings both turns back to the rotation. Cancel after done is refused.
- Rotation reorder keeps the swapped dates. Removing the acceptor cancels the swap.
- An open request expires after its period, and `swap_expired` is logged.
- Activity feed contains each transfer event with the right actor and subject.

## Resolved questions

1. **Payback chore:** same chore only.
2. **Admins:** have no special role in swaps. Anyone can ask, and whoever picks it gets it.
   Only the two people involved can cancel.
3. **Who is asked:** always the whole house. There is no "ask one person" option.
