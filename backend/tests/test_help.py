import threading

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import register
from tests.test_chore_api import API, _setup_house
from tests.test_swaps import _join


def _house(client):
    ann = register(client, "ann@example.com", "Ann")
    house = _setup_house(client, ann)
    bea = _join(client, house, "bea@example.com", "Bea")
    cy = _join(client, house, "cy@example.com", "Cy")
    return house, ann, bea, cy


def _ask(client, house, headers, title="Buy groceries", details=None):
    res = client.post(
        f"{API}/households/{house['id']}/help-requests",
        json={"title": title, "details": details},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _list(client, headers):
    res = client.get(f"{API}/me/help-requests", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _feed(client, house, headers):
    feed = client.get(f"{API}/households/{house['id']}/activity", headers=headers).json()
    return [e for e in feed if e["action"].startswith("help_")]


def test_everyone_in_the_house_sees_a_request_and_anyone_can_mark_it_done(client):
    house, ann, bea, _ = _house(client)
    req = _ask(client, house, ann, details="milk and eggs")
    assert req["status"] == "open" and req["is_mine"]

    [seen] = _list(client, bea)
    assert seen["requester"]["display_name"] == "Ann" and not seen["is_mine"]
    assert seen["details"] == "milk and eggs"

    # Someone in another house doesn't see it.
    dan = register(client, "dan@example.com", "Dan")
    assert _list(client, dan) == []

    res = client.post(f"{API}/help-requests/{req['id']}/done", headers=bea)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "done" and res.json()["done_by"]["display_name"] == "Bea"

    # Ann sees her request is done, and by whom.
    [mine] = _list(client, ann)
    assert mine["status"] == "done" and mine["done_by"]["display_name"] == "Bea"

    actions = [(e["action"], e["actor"]["display_name"]) for e in _feed(client, house, ann)]
    assert actions == [("help_done", "Bea"), ("help_requested", "Ann")]


def test_many_people_marking_done_at_once_only_the_first_counts(client):
    house, ann, bea, cy = _house(client)
    req = _ask(client, house, ann)

    barrier = threading.Barrier(2)
    results: dict[str, int] = {}

    def done(name, headers):
        own = TestClient(app)  # separate connection and DB session per person
        barrier.wait()
        results[name] = own.post(
            f"{API}/help-requests/{req['id']}/done", headers=headers
        ).status_code

    threads = [threading.Thread(target=done, args=a) for a in (("Bea", bea), ("Cy", cy))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results.values()) == [200, 409]
    winner = next(name for name, code in results.items() if code == 200)
    [mine] = _list(client, ann)
    assert mine["done_by"]["display_name"] == winner
    assert [e["action"] for e in _feed(client, house, ann)].count("help_done") == 1

    loser = cy if winner == "Bea" else bea
    res = client.post(f"{API}/help-requests/{req['id']}/done", headers=loser)
    assert res.status_code == 409 and res.json()["detail"] == f"{winner} already marked it done"
    # The same person again is harmless.
    winner_headers = bea if winner == "Bea" else cy
    assert (
        client.post(f"{API}/help-requests/{req['id']}/done", headers=winner_headers).status_code
        == 200
    )


def test_only_the_requester_can_edit_and_only_while_open(client):
    house, ann, bea, _ = _house(client)
    req = _ask(client, house, ann, title="Pick up a package")

    res = client.patch(f"{API}/help-requests/{req['id']}", json={"title": "x"}, headers=bea)
    assert res.status_code == 403

    res = client.patch(
        f"{API}/help-requests/{req['id']}",
        json={"title": "Pick up two packages", "details": "front desk"},
        headers=ann,
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Pick up two packages" and res.json()["details"] == "front desk"
    res = client.patch(f"{API}/help-requests/{req['id']}", json={"details": ""}, headers=ann)
    assert res.json()["details"] is None

    client.post(f"{API}/help-requests/{req['id']}/done", headers=bea)
    res = client.patch(f"{API}/help-requests/{req['id']}", json={"title": "late"}, headers=ann)
    assert res.status_code == 409 and "already did this" in res.json()["detail"]


def test_undo_and_withdraw(client):
    house, ann, bea, cy = _house(client)
    req = _ask(client, house, ann)
    client.post(f"{API}/help-requests/{req['id']}/done", headers=bea)

    # Only the requester or the helper can undo "done".
    assert client.post(f"{API}/help-requests/{req['id']}/reopen", headers=cy).status_code == 403
    res = client.post(f"{API}/help-requests/{req['id']}/reopen", headers=bea)
    assert res.status_code == 200 and res.json()["status"] == "open"
    assert res.json()["done_by"] is None

    # Withdraw: requester only, while open.
    assert client.delete(f"{API}/help-requests/{req['id']}", headers=bea).status_code == 403
    assert client.delete(f"{API}/help-requests/{req['id']}", headers=ann).status_code == 204
    assert _list(client, ann) == []
    assert [e["action"] for e in _feed(client, house, ann)][0] == "help_withdrawn"


def test_validation(client):
    house, ann, _, _ = _house(client)
    res = client.post(
        f"{API}/households/{house['id']}/help-requests", json={"title": "   "}, headers=ann
    )
    assert res.status_code == 422
    req = _ask(client, house, ann, title="  Cook a meal  ")
    assert req["title"] == "Cook a meal"
