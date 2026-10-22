"""Weekly chores, open chores, covering, back-filled missed turns, activity and the report."""

from datetime import UTC, date, datetime, timedelta

from app.services import rotation, suggest
from tests.conftest import register

API = "/api/v1"
ROOMMATES = ["Bea", "Cy", "Dev"]  # 4 people with the admin, Ann
MONDAY = date(2026, 10, 19)


def _house(client, headers) -> dict:
    house = client.post(f"{API}/households", json={"name": "Elm St", "address": "2 Elm St"}, headers=headers).json()
    for name in ROOMMATES:
        client.post(
            f"{API}/households/{house['id']}/members", json={"display_name": name}, headers=headers
        )
    return house


def _members(client, house, headers) -> dict[str, str]:
    res = client.get(f"{API}/households/{house['id']}/members", headers=headers)
    return {m["display_name"]: m["id"] for m in res.json()}


def _today(client, house, headers) -> dict:
    res = client.get(f"{API}/households/{house['id']}/tasks/today", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _chore(client, house, headers, **body) -> dict:
    res = client.post(f"{API}/households/{house['id']}/chores", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _report(client, house, headers, month=None):
    url = f"{API}/households/{house['id']}/report" + (f"?month={month}" if month else "")
    return client.get(url, headers=headers)


def _row(report: dict, chore: str, person: str) -> dict:
    chore_report = next(c for c in report["chores"] if c["chore"]["name"] == chore)
    return next(r for r in chore_report["rows"] if r["member"]["display_name"] == person)


# --- rotation math ----------------------------------------------------------------------------


def test_weekly_rotation_changes_person_once_per_week():
    people = list("ABCD")
    for offset in range(7):
        assert rotation.assignee(people, MONDAY, MONDAY + timedelta(days=offset), 7) == "A"
    assert rotation.assignee(people, MONDAY, MONDAY + timedelta(days=7), 7) == "B"
    assert rotation.assignee(people, MONDAY, MONDAY + timedelta(days=28), 7) == "A"


def test_period_helpers():
    sunday = MONDAY + timedelta(days=6)
    assert rotation.period_start(sunday, "weekly") == MONDAY
    assert rotation.period_end(MONDAY, "weekly") == sunday
    assert rotation.period_start(sunday, "daily") == sunday


def test_ranking_prefers_fewest_this_year_then_this_month():
    year = {"A": 9, "B": 1, "C": 1}
    month = {"A": 0, "B": 1, "C": 0}
    assert suggest.rank(list("ABC"), year, month, {}, seed="x") == ["C", "B", "A"]
    assert suggest.reason(1, 0) == "only 1× this year, none this month"
    assert suggest.reason(0, 0) == "not yet this year, none this month"


def test_ranking_ties_go_to_whoever_did_it_longest_ago():
    last = {"A": date(2026, 10, 18), "B": date(2026, 10, 2)}
    assert suggest.rank(["A", "B", "C"], {}, {}, last, seed="x") == ["C", "B", "A"]  # C: never


def test_ranking_random_tiebreak_is_stable_for_the_day():
    orders = {
        tuple(suggest.rank(list("ABCD"), {}, {}, {}, seed="chore:2026-10-19")) for _ in range(5)
    }
    assert len(orders) == 1


# --- weekly chores ----------------------------------------------------------------------------


def test_weekly_chore_is_one_turn_for_the_whole_week(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    _chore(client, house, ann, name="Clean bathroom", frequency="weekly")

    def bathroom():
        return next(
            t for t in _today(client, house, ann)["tasks"] if t["chore"]["name"] == "Clean bathroom"
        )

    first = bathroom()
    assert first["member"]["display_name"] == "Ann"
    assert first["due_date"] == "2026-10-19" and first["period_end"] == "2026-10-25"

    fake_today.today = MONDAY + timedelta(days=4)  # Friday: same turn
    assert bathroom()["id"] == first["id"]

    fake_today.today = MONDAY + timedelta(days=7)  # next Monday: next person
    assert bathroom()["member"]["display_name"] == "Bea"


def test_weekly_turn_not_done_by_sunday_is_missed(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    _chore(client, house, ann, name="Clean bathroom", frequency="weekly")
    _today(client, house, ann)

    fake_today.today = MONDAY + timedelta(days=8)
    report = _report(client, house, ann).json()
    assert _row(report, "Clean bathroom", "Ann")["missed"] == 1
    overdue = client.get(f"{API}/me/tasks/today", headers=ann).json()["overdue"]
    assert "Clean bathroom" in [t["chore"]["name"] for t in overdue]


# --- covering & activity ----------------------------------------------------------------------


def test_anyone_can_mark_done_for_someone_else_and_it_is_recorded(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    people = _members(client, house, ann)
    cooking = next(
        t for t in _today(client, house, ann)["tasks"] if t["chore"]["name"] == "Cooking"
    )

    # Ann records that Cy cooked on her turn.
    res = client.post(
        f"{API}/tasks/{cooking['id']}/complete",
        json={"completed_by_member_id": people["Cy"]},
        headers=ann,
    )
    assert res.status_code == 200, res.text
    assert res.json()["completed_by"]["display_name"] == "Cy"

    report = _report(client, house, ann).json()
    assert _row(report, "Cooking", "Cy")["done"] == 1
    assert _row(report, "Cooking", "Cy")["covered_for_others"] == 1
    assert _row(report, "Cooking", "Ann")["covered_by_others"] == 1
    assert _row(report, "Cooking", "Ann")["done"] == 0

    client.post(f"{API}/tasks/{cooking['id']}/reopen", headers=ann)
    feed = client.get(f"{API}/households/{house['id']}/activity", headers=ann).json()
    assert [e["action"] for e in feed[:2]] == ["reopened", "completed"]
    completed = feed[1]
    assert completed["actor"]["display_name"] == "Ann"
    assert completed["subject"]["display_name"] == "Cy"
    assert completed["assignee"]["display_name"] == "Ann"
    assert completed["chore_name"] == "Cooking"
    assert {"member_added"} <= {e["action"] for e in feed}


# --- open chores ------------------------------------------------------------------------------


def test_open_chore_is_logged_by_whoever_does_it(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    people = _members(client, house, ann)
    garbage = next(
        c
        for c in client.get(f"{API}/households/{house['id']}/chores", headers=ann).json()
        if c["name"] == "Dispose garbage"
    )
    res = client.patch(
        f"{API}/chores/{garbage['id']}",
        json={"assignment_mode": "open", "target_per_week": 4},
        headers=ann,
    )
    assert res.status_code == 200 and res.json()["assignment_mode"] == "open"

    today = _today(client, house, ann)
    assert "Dispose garbage" not in [t["chore"]["name"] for t in today["tasks"]]
    assert [o["chore"]["name"] for o in today["open"]] == ["Dispose garbage"]

    url = f"{API}/chores/{garbage['id']}/logs"
    assert client.post(url, headers=ann).status_code == 201
    assert client.post(url, json={"member_id": people["Cy"]}, headers=ann).status_code == 201
    fake_today.today += timedelta(days=1)
    log = client.post(url, json={"member_id": people["Cy"]}, headers=ann).json()

    open_chore = _today(client, house, ann)["open"][0]
    assert open_chore["this_week_count"] == 3
    assert open_chore["last_done"]["member"]["display_name"] == "Cy"
    # Buttons: everyone, fewest this year first. Ann 1, Cy 2, Bea and Dev 0.
    people = [(p["member"]["display_name"], p["this_year"]) for p in open_chore["people"]]
    assert sorted(people[:2]) == [("Bea", 0), ("Dev", 0)]
    assert people[2:] == [("Ann", 1), ("Cy", 2)]
    assert open_chore["suggested"]["display_name"] == people[0][0]
    assert open_chore["suggested_reason"] == "not yet this year, none this month"

    report = _report(client, house, ann).json()
    rows = next(c for c in report["chores"] if c["chore"]["name"] == "Dispose garbage")["rows"]
    assert [(r["member"]["display_name"], r["done"]) for r in rows[:2]] == [("Cy", 2), ("Ann", 1)]
    assert rows[0]["turns"] is None  # open chores have no turns

    assert client.delete(f"{API}/chore-logs/{log['id']}", headers=ann).status_code == 204
    assert _report(client, house, ann).json()["leaderboard"][0]["done"] >= 1
    actions = [
        e["action"]
        for e in client.get(f"{API}/households/{house['id']}/activity", headers=ann).json()
    ]
    assert actions[0] == "log_removed" and actions.count("logged") == 3


def test_rotation_chore_rejects_logs(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    cooking = client.get(f"{API}/households/{house['id']}/chores", headers=ann).json()[0]
    assert client.post(f"{API}/chores/{cooking['id']}/logs", headers=ann).status_code == 400


# --- missed turns & pausing -------------------------------------------------------------------


def test_days_nobody_opened_the_app_count_as_missed(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    _today(client, house, ann)  # day 1 recorded

    fake_today.today = MONDAY + timedelta(days=4)  # nobody opened the app for 3 days
    report = _report(client, house, ann).json()
    cooking = next(c for c in report["chores"] if c["chore"]["name"] == "Cooking")
    assert cooking["total_missed"] == 4  # Mon..Thu, today (Fri) is not over yet
    assert sum(r["turns"] for r in cooking["rows"]) == 5


def test_paused_days_are_not_counted_as_missed(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    cooking = client.get(f"{API}/households/{house['id']}/chores", headers=ann).json()[0]
    _today(client, house, ann)
    client.patch(f"{API}/chores/{cooking['id']}", json={"is_active": False}, headers=ann)

    fake_today.today = MONDAY + timedelta(days=5)
    client.patch(f"{API}/chores/{cooking['id']}", json={"is_active": True}, headers=ann)
    report = _report(client, house, ann).json()
    row = next(c for c in report["chores"] if c["chore"]["name"] == "Cooking")
    assert row["total_missed"] == 0  # day 1's pending turn was dropped when paused
    assert sum(r["turns"] for r in row["rows"]) == 1  # only today since resuming


# --- report permissions -----------------------------------------------------------------------


def test_current_month_for_everyone_past_months_for_admins(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    bea = register(client, "bea@example.com", "Bea")
    client.post(f"{API}/invites/{house['invite_code']}/accept", json={}, headers=bea)
    _today(client, house, ann)

    fake_today.today = date(2026, 11, 3)
    assert _report(client, house, bea).status_code == 200
    assert _report(client, house, bea, "2026-10").status_code == 403
    past = _report(client, house, ann, "2026-10")
    assert past.status_code == 200 and past.json()["is_current"] is False

    months = client.get(f"{API}/households/{house['id']}/report/months", headers=ann).json()
    assert months["months"][:2] == ["2026-11", "2026-10"]
    assert (
        client.get(f"{API}/households/{house['id']}/report/months", headers=bea).status_code == 403
    )


def test_activity_for_a_month_shows_who_marked_what(client, fake_today):
    # Events are stamped with the real clock, so run "today" in the real current month.
    real_today = datetime.now(UTC).date()
    fake_today.today = real_today
    this_month = real_today.strftime("%Y-%m")
    next_month_start = (real_today.replace(day=28) + timedelta(days=4)).replace(day=1)

    ann = register(client, "ann@example.com", "Ann")
    house = _house(client, ann)
    people = _members(client, house, ann)
    bea = register(client, "bea@example.com", "Bea")
    client.post(
        f"{API}/invites/{house['invite_code']}/accept",
        json={"member_id": people["Bea"]},
        headers=bea,
    )

    task = _today(client, house, ann)["tasks"][0]
    # Bea records that Cy did someone's turn.
    client.post(
        f"{API}/tasks/{task['id']}/complete",
        json={"completed_by_member_id": people["Cy"]},
        headers=bea,
    )

    url = f"{API}/households/{house['id']}/activity?month={this_month}"
    events = client.get(url, headers=bea).json()
    done = next(e for e in events if e["action"] == "completed")
    assert (done["actor"]["display_name"], done["subject"]["display_name"]) == ("Bea", "Cy")
    assert done["assignee"]["display_name"] == task["member"]["display_name"]
    assert {"member_added", "member_joined"} <= {e["action"] for e in events}

    # Next month: this month becomes history -> admins only; the new month starts empty.
    fake_today.today = next_month_start + timedelta(days=1)
    assert client.get(url, headers=bea).status_code == 403
    assert len(client.get(url, headers=ann).json()) == len(events)
    new_month = f"{API}/households/{house['id']}/activity?month={next_month_start:%Y-%m}"
    assert client.get(new_month, headers=bea).json() == []
