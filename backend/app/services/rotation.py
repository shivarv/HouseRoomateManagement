"""Pure round-robin math. No database access, so it is trivially unit-testable.

A chore with ordered rotation M (length N) and start date S is assigned on date D to
    M[(D - S).days mod N]
"""

from collections.abc import Sequence
from datetime import date, timedelta


def assignee_index(start: date, on: date, size: int) -> int | None:
    if size == 0:
        return None
    return (on - start).days % size


def assignee[T](order: Sequence[T], start: date, on: date) -> T | None:
    index = assignee_index(start, on, len(order))
    return None if index is None else order[index]


def staggered_start(today: date, existing_chore_count: int) -> date:
    """Shift each new chore by one slot so one person doesn't get every chore on the same day."""
    return today - timedelta(days=existing_chore_count)


def rebased_start[T](old: Sequence[T], new: Sequence[T], start: date, today: date) -> date:
    """Start date for `new` that keeps today's person on duty today.

    If today's person is no longer in the rotation, the next person (in the old order) who is
    still in it takes today, so the rotation continues instead of jumping.
    """
    if not old or not new:
        return start
    current = (today - start).days % len(old)
    for step in range(len(old)):
        candidate = old[(current + step) % len(old)]
        if candidate in new:
            return today - timedelta(days=list(new).index(candidate))
    return today
