"""Pure round-robin math. No database access, so it is trivially unit-testable.

A chore comes up once per *period*: a day (daily) or a Mon–Sun week (weekly). Dates are first
normalised to the start of their period. With ordered rotation M (length N), rotation start S and
period length `step` days, the chore is assigned for date D to
    M[((period_start(D) - S).days // step) mod N]
"""

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

Frequency = Literal["daily", "weekly"]


def step_days(frequency: Frequency) -> int:
    return 7 if frequency == "weekly" else 1


def period_start(day: date, frequency: Frequency) -> date:
    return day - timedelta(days=day.weekday()) if frequency == "weekly" else day


def period_end(day: date, frequency: Frequency) -> date:
    return period_start(day, frequency) + timedelta(days=step_days(frequency) - 1)


def assignee_index(start: date, on: date, size: int, step: int = 1) -> int | None:
    if size == 0:
        return None
    return ((on - start).days // step) % size


def assignee[T](order: Sequence[T], start: date, on: date, step: int = 1) -> T | None:
    index = assignee_index(start, on, len(order), step)
    return None if index is None else order[index]


def next_turn[T](
    order: Sequence[T], start: date, current_period: date, who: T, step: int = 1
) -> date | None:
    """Start of the first period after the current one in which `who` is on duty."""
    if who not in order:
        return None
    current = ((current_period - start).days // step) % len(order)
    ahead = (list(order).index(who) - current) % len(order) or len(order)
    return current_period + timedelta(days=ahead * step)


def staggered_start(current_period: date, existing_chore_count: int, step: int = 1) -> date:
    """Shift each new chore by one slot so one person doesn't get every chore in the same period."""
    return current_period - timedelta(days=existing_chore_count * step)


def rebased_start[T](
    old: Sequence[T], new: Sequence[T], start: date, current_period: date, step: int = 1
) -> date:
    """Start date for `new` that keeps the current period's person on duty.

    If that person is no longer in the rotation, the next person (in the old order) who is
    still in it takes over, so the rotation continues instead of jumping.
    """
    if not old or not new:
        return start
    current = ((current_period - start).days // step) % len(old)
    for offset in range(len(old)):
        candidate = old[(current + offset) % len(old)]
        if candidate in new:
            return current_period - timedelta(days=list(new).index(candidate) * step)
    return current_period
