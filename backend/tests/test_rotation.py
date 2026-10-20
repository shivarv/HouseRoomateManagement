from datetime import date, timedelta

from app.services import rotation

PEOPLE = list("ABCDEFGH")
DAY1 = date(2026, 10, 19)


def test_round_robin_cycles_through_everyone_and_repeats():
    days = [rotation.assignee(PEOPLE, DAY1, DAY1 + timedelta(days=i)) for i in range(17)]
    assert "".join(days) == "ABCDEFGHABCDEFGHA"


def test_empty_rotation_has_no_assignee():
    assert rotation.assignee([], DAY1, DAY1) is None


def test_dates_before_start_still_follow_the_cycle():
    assert rotation.assignee(PEOPLE, DAY1, DAY1 - timedelta(days=1)) == "H"


def test_staggered_chores_give_different_people_the_same_day():
    starts = [rotation.staggered_start(DAY1, k) for k in range(3)]
    assert [rotation.assignee(PEOPLE, s, DAY1) for s in starts] == ["A", "B", "C"]
    tomorrow = DAY1 + timedelta(days=1)
    assert [rotation.assignee(PEOPLE, s, tomorrow) for s in starts] == ["B", "C", "D"]


def test_rebase_keeps_todays_person_when_someone_is_added():
    start = DAY1 - timedelta(days=2)  # today is C
    new = [*PEOPLE, "I"]
    new_start = rotation.rebased_start(PEOPLE, new, start, DAY1)
    assert rotation.assignee(new, new_start, DAY1) == "C"
    assert rotation.assignee(new, new_start, DAY1 + timedelta(days=1)) == "D"


def test_rebase_hands_today_to_next_person_when_todays_person_leaves():
    start = DAY1 - timedelta(days=2)  # today is C
    new = [p for p in PEOPLE if p != "C"]
    new_start = rotation.rebased_start(PEOPLE, new, start, DAY1)
    assert rotation.assignee(new, new_start, DAY1) == "D"


def test_rebase_after_reorder_continues_from_todays_person():
    start = DAY1  # today is A
    new = ["H", "G", "F", "E", "D", "C", "B", "A"]
    new_start = rotation.rebased_start(PEOPLE, new, start, DAY1)
    assert rotation.assignee(new, new_start, DAY1) == "A"
    assert rotation.assignee(new, new_start, DAY1 + timedelta(days=1)) == "H"
