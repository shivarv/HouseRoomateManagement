import threading
from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import register
from tests.test_chore_api import API, _setup_house

# Cooking rotates Ann, Bea, Cy, Dev, Eli, Fay, Gus, Hal starting Mon 2026-10-19 (Ann's day).
BASELINE = ["Ann", "Bea", "Cy", "Dev", "Eli", "Fay", "Gus", "Hal", "Ann"]


def _join(client, house, email, name) -> dict:
    headers = register(client, email, name)
    preview = client.get(f"{API}/invites/{house['invite_code']}", headers=headers).json()
    member = next(m for m in preview["unclaimed_members"] if m["display_name"] == name)
    res = client.post(
        f"{API}/invites/{house['invite_code']}/accept",
        json={"member_id": member["id"]},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return headers


def _house(client):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)
    bea = _join(client, house, "bea@example.com", "Bea")
    cy = _join(client, house, "cy@example.com", "Cy")
    cooking = next(
        c
        for c in client.get(f"{API}/households/{house['id']}/chores", headers=ann).json()
        if c["name"] == "Cooking"
    )
    return house, cooking, ann, bea, cy


def _cooking(client, house, headers, days=9) -> list[str]:
    res = client.get(f"{API}/households/{house['id']}/schedule?days={days}", headers=headers)
    assert res.status_code == 200, res.text
    return [
        next(s["member"]["display_name"] for s in d["slots"] if s["chore"]["name"] == "Cooking")
        for d in res.json()["days"]
    ]


def _ask(client, cooking, headers, day="2026-10-19", note=None):
    return client.post(
        f"{API}/chores/{cooking['id']}/swaps", json={"due_date": day, "note": note}, headers=headers
    )


def _feed(client, house, headers, action):
    feed = client.get(f"{API}/households/{house['id']}/activity", headers=headers).json()
    return [e for e in feed if e["action"] == action]


def test_swap_changes_only_two_turns_and_the_cycle_continues(client, fake_today):
    house, cooking, ann, bea, _ = _house(client)
    assert _cooking(client, house, ann) == BASELINE

    res = _ask(client, cooking, ann, note="travelling")
    assert res.status_code == 201, res.text
    swap = res.json()
    assert swap["status"] == "open" and swap["is_mine"] and not swap["can_accept"]

    # Bea sees it, and which of her turns she'd give back.
    [offer] = client.get(f"{API}/me/swaps", headers=bea).json()
    assert offer["can_accept"] and offer["payback_preview"] == "2026-10-20"

    res = client.post(f"{API}/swaps/{swap['id']}/accept", headers=bea)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "accepted" and res.json()["payback_date"] == "2026-10-20"

    # Mon and Tue swap; from Wed on, the rotation is exactly what it was.
    assert _cooking(client, house, ann) == ["Bea", "Ann", *BASELINE[2:]]

    today = client.get(f"{API}/households/{house['id']}/tasks/today", headers=ann).json()
    task = next(t for t in today["tasks"] if t["chore"]["name"] == "Cooking")
    assert task["member"]["display_name"] == "Bea"
    assert task["swap"]["role"] == "given" and task["swap"]["other"]["display_name"] == "Ann"
    assert task["next_assignee"]["display_name"] == "Ann"

    upcoming = client.get(f"{API}/me/tasks/today", headers=ann).json()["upcoming"]
    assert next(u for u in upcoming if u["chore"]["name"] == "Cooking")["due_date"] == "2026-10-20"

    [requested] = _feed(client, house, ann, "swap_requested")
    assert requested["actor"]["display_name"] == "Ann" and requested["detail"] == "travelling"
    [accepted] = _feed(client, house, ann, "swap_accepted")
    assert accepted["actor"]["display_name"] == "Bea"
    assert accepted["subject"]["display_name"] == "Ann"
    assert accepted["detail"] == "2026-10-20"

    # Tomorrow Ann is on duty for the payback turn.
    fake_today.today += timedelta(days=1)
    mine = client.get(f"{API}/me/tasks/today", headers=ann).json()["tasks"]
    payback = next(t for t in mine if t["chore"]["name"] == "Cooking")
    assert payback["swap"]["role"] == "payback"
    assert payback["swap"]["other"]["display_name"] == "Bea"


def test_many_people_accepting_at_once_only_the_first_wins(client, fake_today):
    house, cooking, ann, bea, cy = _house(client)
    swap = _ask(client, cooking, ann).json()

    barrier = threading.Barrier(2)
    results: dict[str, int] = {}

    def accept(name, headers):
        own = TestClient(app)  # separate connection and DB session per person
        barrier.wait()
        results[name] = own.post(f"{API}/swaps/{swap['id']}/accept", headers=headers).status_code

    threads = [threading.Thread(target=accept, args=a) for a in (("Bea", bea), ("Cy", cy))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results.values()) == [200, 409]
    winner = next(name for name, code in results.items() if code == 200)
    assert len(_feed(client, house, ann, "swap_accepted")) == 1
    assert _cooking(client, house, ann)[0] == winner

    # The loser is told who already has it, and nothing changes.
    loser = cy if winner == "Bea" else bea
    res = client.post(f"{API}/swaps/{swap['id']}/accept", headers=loser)
    assert res.status_code == 409 and res.json()["detail"] == f"{winner} already took it"
    assert _cooking(client, house, ann)[0] == winner


def test_repeated_clicks_are_harmless(client, fake_today):
    house, cooking, ann, bea, _ = _house(client)
    first = _ask(client, cooking, ann).json()
    assert _ask(client, cooking, ann).json()["id"] == first["id"]  # one request, not two
    assert len(_feed(client, house, ann, "swap_requested")) == 1

    for _ in range(2):
        res = client.post(f"{API}/swaps/{first['id']}/accept", headers=bea)
        assert res.status_code == 200
    assert len(_feed(client, house, ann, "swap_accepted")) == 1


def test_a_turn_can_be_swapped_again(client, fake_today):
    house, cooking, ann, bea, cy = _house(client)
    first = _ask(client, cooking, ann).json()
    client.post(f"{API}/swaps/{first['id']}/accept", headers=bea)

    # Bea now owns Monday and passes it on; Cy's next turn (Wed) becomes Bea's.
    second = _ask(client, cooking, bea).json()
    res = client.post(f"{API}/swaps/{second['id']}/accept", headers=cy)
    assert res.status_code == 200 and res.json()["payback_date"] == "2026-10-21"
    assert _cooking(client, house, ann) == ["Cy", "Ann", "Bea", *BASELINE[3:]]

    # The older swap can't be undone while the later one builds on it.
    res = client.post(f"{API}/swaps/{first['id']}/cancel", headers=ann)
    assert res.status_code == 400 and "later swap" in res.json()["detail"]

    assert client.post(f"{API}/swaps/{second['id']}/cancel", headers=cy).status_code == 200
    assert _cooking(client, house, ann) == ["Bea", "Ann", *BASELINE[2:]]
    assert client.post(f"{API}/swaps/{first['id']}/cancel", headers=ann).status_code == 200
    assert _cooking(client, house, ann) == BASELINE


def test_cancelling(client, fake_today):
    house, cooking, ann, bea, cy = _house(client)
    swap = _ask(client, cooking, ann).json()

    # Only the requester can withdraw an open request.
    assert client.post(f"{API}/swaps/{swap['id']}/cancel", headers=bea).status_code == 403
    assert client.post(f"{API}/swaps/{swap['id']}/cancel", headers=ann).status_code == 200
    assert client.post(f"{API}/swaps/{swap['id']}/accept", headers=bea).status_code == 409

    # After accepting, either side can undo it until the turn is done.
    swap = _ask(client, cooking, ann).json()
    client.post(f"{API}/swaps/{swap['id']}/accept", headers=bea)
    assert client.post(f"{API}/swaps/{swap['id']}/cancel", headers=cy).status_code == 403
    assert client.post(f"{API}/swaps/{swap['id']}/cancel", headers=bea).status_code == 200
    assert _cooking(client, house, ann) == BASELINE
    cancelled = _feed(client, house, ann, "swap_cancelled")
    assert cancelled[0]["actor"]["display_name"] == "Bea"
    assert cancelled[0]["subject"]["display_name"] == "Ann"

    swap = _ask(client, cooking, ann).json()
    client.post(f"{API}/swaps/{swap['id']}/accept", headers=bea)
    task = next(
        t
        for t in client.get(f"{API}/households/{house['id']}/tasks/today", headers=bea).json()[
            "tasks"
        ]
        if t["chore"]["name"] == "Cooking"
    )
    client.post(f"{API}/tasks/{task['id']}/complete", headers=bea)
    res = client.post(f"{API}/swaps/{swap['id']}/cancel", headers=ann)
    assert res.status_code == 400 and "already done" in res.json()["detail"]


def test_who_can_ask_and_accept(client, fake_today):
    house, cooking, ann, bea, _ = _house(client)
    assert _ask(client, cooking, bea).status_code == 400  # Monday is Ann's turn, not Bea's
    assert _ask(client, cooking, ann, day="2026-10-18").status_code == 400  # already over

    swap = _ask(client, cooking, ann).json()
    res = client.post(f"{API}/swaps/{swap['id']}/accept", headers=ann)
    assert res.status_code == 400 and res.json()["detail"] == "You can't take your own swap"

    # A future turn can be offered too.
    assert _ask(client, cooking, ann, day="2026-10-27").status_code == 201


def test_unanswered_request_expires(client, fake_today):
    house, cooking, ann, bea, _ = _house(client)
    swap = _ask(client, cooking, ann).json()

    fake_today.today += timedelta(days=1)
    assert client.get(f"{API}/me/swaps", headers=bea).json() == []
    assert client.post(f"{API}/swaps/{swap['id']}/accept", headers=bea).status_code == 409
    [expired] = _feed(client, house, ann, "swap_expired")
    assert expired["subject"]["display_name"] == "Ann"


def test_removing_someone_withdraws_their_swaps(client, fake_today):
    house, cooking, ann, bea, _ = _house(client)
    swap = _ask(client, cooking, ann).json()
    client.post(f"{API}/swaps/{swap['id']}/accept", headers=bea)

    members = client.get(f"{API}/households/{house['id']}/members", headers=ann).json()
    bea_id = next(m["id"] for m in members if m["display_name"] == "Bea")
    assert client.delete(f"{API}/members/{bea_id}", headers=ann).status_code == 204

    # Monday is Ann's again, and Bea is out of the rotation.
    assert _cooking(client, house, ann)[0] == "Ann"
    assert "Bea" not in _cooking(client, house, ann)
    assert _feed(client, house, ann, "swap_cancelled")[0]["detail"] == "withdrawn"
