"""Fairness ranking for open chores (e.g. garbage). Pure functions, no database access.

People are ranked by fewest times this year, then fewest this month, then longest since they last
did it (never counts as longest). Remaining ties are broken randomly, but seeded with chore + day so
the order stays the same all day instead of shuffling on every refresh. The first person is the
suggestion for who should do it next: a hint, not an assignment.
"""

import random
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any


def rank[T: Any](
    people: Sequence[T],
    year_counts: Mapping[T, int],
    month_counts: Mapping[T, int],
    last_done: Mapping[T, date],
    seed: str,
) -> list[T]:
    tiebreak = {p: random.Random(f"{seed}:{p}").random() for p in people}
    return sorted(
        people,
        key=lambda p: (
            year_counts.get(p, 0),
            month_counts.get(p, 0),
            last_done.get(p, date.min),
            tiebreak[p],
        ),
    )


def reason(year: int, month: int) -> str:
    year_text = "not yet this year" if year == 0 else f"only {year}× this year"
    month_text = "none this month" if month == 0 else f"{month}× this month"
    return f"{year_text}, {month_text}"
