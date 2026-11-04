from datetime import timedelta

from tests.conftest import register

API = "/api/v1"
ROOMMATES = ["Bea", "Cy", "Dev", "Eli", "Fay", "Gus", "Hal"]


def _setup_house(client, headers) -> dict:
    """Admin 'Ann' plus 7 roommates added by name -> 8 people, 3 default chores."""
    res = client.post(
        f"{API}/households", json={"name": "Maple St", "address": "1 Maple St", "timezone": "UTC"}, headers=headers
    )
    assert res.status_code == 201, res.text
    house = res.json()
    for name in ROOMMATES:
        res = client.post(
            f"{API}/households/{house['id']}/members", json={"display_name": name, "phone": "+1 617 555 0100"}, headers=headers
        )
        assert res.status_code == 201, res.text
    return house


def _today_by_chore(client, house_id, headers) -> dict[str, str]:
    res = client.get(f"{API}/households/{house_id}/tasks/today", headers=headers)
    assert res.status_code == 200, res.text
    return {t["chore"]["name"]: t["member"]["display_name"] for t in res.json()["tasks"]}


def test_default_chores_rotate_round_robin_and_are_staggered(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)

    chores = client.get(f"{API}/households/{house['id']}/chores", headers=ann).json()
    assert [c["name"] for c in chores] == ["Cooking", "Clean hall", "Dispose garbage"]
    assert [c["assignment_mode"] for c in chores] == ["rotation", "rotation", "open"]
    assert [m["display_name"] for m in chores[0]["rotation"]] == ["Ann", *ROOMMATES]

    # Garbage is open to anyone, so only the two rotation chores have turns.
    assert _today_by_chore(client, house["id"], ann) == {"Cooking": "Ann", "Clean hall": "Bea"}

    fake_today.today += timedelta(days=1)
    assert _today_by_chore(client, house["id"], ann) == {"Cooking": "Bea", "Clean hall": "Cy"}

    fake_today.today += timedelta(days=8)  # one full cycle of 8 people later
    assert _today_by_chore(client, house["id"], ann)["Cooking"] == "Bea"


def test_schedule_projects_future_days(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)
    res = client.get(f"{API}/households/{house['id']}/schedule?days=9", headers=ann)
    assert res.status_code == 200, res.text
    cooking = [
        next(s["member"]["display_name"] for s in day["slots"] if s["chore"]["name"] == "Cooking")
        for day in res.json()["days"]
    ]
    assert cooking == ["Ann", *ROOMMATES, "Ann"]


def test_my_tasks_today_is_the_reminder_for_the_logged_in_person(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)

    # Bea signs up and claims her name via the invite code.
    bea = register(client, "bea@example.com", "Bea")
    preview = client.get(f"{API}/invites/{house['invite_code']}", headers=bea).json()
    bea_member = next(m for m in preview["unclaimed_members"] if m["display_name"] == "Bea")
    res = client.post(
        f"{API}/invites/{house['invite_code']}/accept",
        json={"member_id": bea_member["id"]},
        headers=bea,
    )
    assert res.status_code == 200, res.text

    mine = client.get(f"{API}/me/tasks/today", headers=bea).json()
    assert [t["chore"]["name"] for t in mine["tasks"]] == ["Clean hall"]
    task = mine["tasks"][0]
    assert task["is_mine"] and task["next_assignee"]["display_name"] == "Cy"

    # My day also shows everyone else's turns and when my next turns are.
    assert [(t["chore"]["name"], t["member"]["display_name"]) for t in mine["others"]] == [
        ("Cooking", "Ann")
    ]
    assert [(u["chore"]["name"], u["due_date"]) for u in mine["upcoming"]] == [
        ("Cooking", "2026-10-20"),  # tomorrow
        ("Clean hall", "2026-10-27"),  # today is mine, so the next one is 8 days later
    ]

    res = client.post(f"{API}/tasks/{task['id']}/complete", headers=bea)
    assert res.status_code == 200 and res.json()["status"] == "done"

    assert res.json()["completed_by"]["display_name"] == "Bea"

    # Bea covers Ann's cooking: allowed, and recorded as done by Bea.
    ann_task = client.get(f"{API}/me/tasks/today", headers=ann).json()["tasks"][0]
    res = client.post(f"{API}/tasks/{ann_task['id']}/complete", headers=bea)
    assert res.status_code == 200
    assert res.json()["member"]["display_name"] == "Ann"
    assert res.json()["completed_by"]["display_name"] == "Bea"


def test_marking_someone_elses_turn_as_done_by_them_is_in_the_history(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)

    # "It's done" on Bea's turn: Ann records that Bea did it.
    today = client.get(f"{API}/households/{house['id']}/tasks/today", headers=ann).json()
    hall = next(t for t in today["tasks"] if t["chore"]["name"] == "Clean hall")
    res = client.post(
        f"{API}/tasks/{hall['id']}/complete",
        json={"completed_by_member_id": hall["member"]["id"]},
        headers=ann,
    )
    assert res.status_code == 200, res.text
    assert res.json()["completed_by"]["display_name"] == "Bea"

    feed = client.get(f"{API}/households/{house['id']}/activity", headers=ann).json()
    event = next(e for e in feed if e["action"] == "completed")
    assert event["chore_name"] == "Clean hall"
    assert event["actor"]["display_name"] == "Ann"
    assert event["subject"]["display_name"] == "Bea"
    assert event["assignee"]["display_name"] == "Bea"


def test_missed_task_shows_as_overdue_and_rotation_keeps_moving(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)
    assert (
        client.get(f"{API}/me/tasks/today", headers=ann).json()["tasks"][0]["chore"]["name"]
        == "Cooking"
    )

    fake_today.today += timedelta(days=1)
    mine = client.get(f"{API}/me/tasks/today", headers=ann).json()
    assert [t["chore"]["name"] for t in mine["overdue"]] == ["Cooking"]
    assert _today_by_chore(client, house["id"], ann)["Cooking"] == "Bea"


def test_removing_todays_person_hands_the_task_to_the_next_person(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)
    _today_by_chore(client, house["id"], ann)  # generates day-1 history

    fake_today.today += timedelta(days=1)  # Cooking: Bea, Clean hall: Cy
    members = client.get(f"{API}/households/{house['id']}/members", headers=ann).json()
    bea = next(m for m in members if m["display_name"] == "Bea")
    assert client.delete(f"{API}/members/{bea['id']}", headers=ann).status_code == 204

    today = _today_by_chore(client, house["id"], ann)
    assert today["Cooking"] == "Cy"
    assert today["Clean hall"] == "Cy"

    fake_today.today += timedelta(days=1)
    assert _today_by_chore(client, house["id"], ann)["Cooking"] == "Dev"


def test_only_admin_can_change_rotation(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)
    bea = register(client, "bea@example.com", "Bea")
    client.post(f"{API}/invites/{house['invite_code']}/accept", json={}, headers=bea)

    chore = client.get(f"{API}/households/{house['id']}/chores", headers=ann).json()[0]
    reversed_ids = [m["id"] for m in reversed(chore["rotation"])]
    url = f"{API}/chores/{chore['id']}/rotation"
    assert client.put(url, json={"member_ids": reversed_ids}, headers=bea).status_code == 403

    res = client.put(url, json={"member_ids": reversed_ids}, headers=ann)
    assert res.status_code == 200, res.text
    assert res.json()["rotation"][0]["display_name"] == chore["rotation"][-1]["display_name"]


def test_requires_auth(client):
    assert client.get(f"{API}/me/tasks/today").status_code == 401


def test_unexpected_crash_is_a_readable_500_with_cors(client, fake_today, monkeypatch):
    from app.services import tasks

    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)

    def boom(*args, **kwargs):
        raise RuntimeError("database is missing a table")

    monkeypatch.setattr(tasks, "sync", boom)
    res = client.get(
        f"{API}/households/{house['id']}/tasks/today",
        headers={**ann, "Origin": "http://localhost:5173"},
    )
    assert res.status_code == 500
    ref = res.json()["error_id"]
    assert ref.startswith("req_") and res.json()["detail"] == f"Something went wrong on the server (ref {ref})"
    assert res.headers["x-request-id"] == ref
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_double_taps_on_done_and_open_chores_count_once(client, fake_today):
    from tests.test_help import _house

    house, ann, bea, _ = _house(client)
    hid = house["id"]
    tasks = client.get(f"{API}/households/{hid}/tasks/today", headers=ann).json()["tasks"]
    hall = next(t for t in tasks if t["chore"]["name"] == "Clean hall")
    for _ in range(3):
        assert client.post(f"{API}/tasks/{hall['id']}/complete", headers=ann).status_code == 200
    # Saying someone else did it still changes who.
    res = client.post(
        f"{API}/tasks/{hall['id']}/complete",
        json={"completed_by_member_id": hall["member"]["id"]},
        headers=ann,
    )
    assert res.json()["completed_by"]["id"] == hall["member"]["id"]
    for _ in range(2):
        client.post(f"{API}/tasks/{hall['id']}/reopen", headers=ann)

    chores = client.get(f"{API}/households/{hid}/chores", headers=ann).json()
    garbage = next(c for c in chores if c["name"] == "Dispose garbage")
    first = client.post(f"{API}/chores/{garbage['id']}/logs", headers=bea).json()
    again = client.post(f"{API}/chores/{garbage['id']}/logs", headers=bea).json()
    assert again["id"] == first["id"]

    feed = client.get(f"{API}/households/{hid}/activity", headers=ann).json()
    actions = [e["action"] for e in feed if e["chore_name"] in ("Clean hall", "Dispose garbage")]
    assert sorted(actions) == ["completed", "completed", "logged", "reopened"]
