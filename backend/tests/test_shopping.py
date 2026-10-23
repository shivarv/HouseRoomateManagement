import threading

from fastapi.testclient import TestClient

from app.main import app
from app.services.shopping import guess_category
from tests.test_chore_api import API
from tests.test_help import _house


def _add(client, house, headers, name, **extra):
    return client.post(
        f"{API}/households/{house['id']}/shopping", json={"name": name, **extra}, headers=headers
    )


def _list(client, house, headers):
    res = client.get(f"{API}/households/{house['id']}/shopping", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _feed(client, house, headers):
    feed = client.get(f"{API}/households/{house['id']}/activity", headers=headers).json()
    return [(e["action"], e["detail"]) for e in feed if e["action"].startswith("shopping_")]


def test_add_guesses_category_and_never_duplicates(client):
    house, ann, bea, _ = _house(client)
    res = _add(client, house, ann, "Eggs", quantity="2 dozen")
    assert res.status_code == 201
    eggs = res.json()
    assert eggs["category"] == "groceries" and eggs["quantity"] == "2 dozen"
    assert eggs["added_by"]["display_name"] == "Ann" and eggs["status"] == "needed"

    # Same thing, different capitalisation and spacing: the existing item comes back.
    again = _add(client, house, bea, "  eggs ")
    assert again.status_code == 200 and again.json()["id"] == eggs["id"]

    assert _add(client, house, ann, "Shampoo").json()["category"] == "toiletries"
    assert _add(client, house, ann, "Garbage bags").json()["category"] == "cleaning"
    assert _add(client, house, ann, "Tissues").json()["category"] == "household"
    assert _add(client, house, ann, "Mystery", category="cleaning").json()["category"] == "cleaning"

    names = [i["name"] for i in _list(client, house, bea)["needed"]]
    assert names == ["Eggs", "Shampoo", "Garbage bags", "Tissues", "Mystery"]
    assert _feed(client, house, ann)[-1] == ("shopping_added", "Eggs")


def test_category_guesses():
    assert guess_category("Toilet paper") == "household"  # not groceries, despite "oil"
    assert guess_category("Washing soap") == "cleaning"
    assert guess_category("Sunflower oil") == "groceries"
    assert guess_category("Something odd") == "other"


def test_many_people_marking_bought_at_once_only_the_first_counts(client):
    house, ann, bea, cy = _house(client)
    rice = _add(client, house, ann, "Rice").json()

    barrier = threading.Barrier(2)
    results: dict[str, int] = {}

    def buy(name, headers):
        own = TestClient(app)  # separate connection and DB session per person
        barrier.wait()
        results[name] = own.post(f"{API}/shopping/{rice['id']}/bought", headers=headers).status_code

    threads = [threading.Thread(target=buy, args=a) for a in (("Bea", bea), ("Cy", cy))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results.values()) == [200, 409]
    winner = next(name for name, code in results.items() if code == 200)
    [bought] = _list(client, house, ann)["recently_bought"]
    assert bought["bought_by"]["display_name"] == winner
    assert [a for a, _ in _feed(client, house, ann)].count("shopping_bought") == 1


def test_adding_the_same_thing_at_once_makes_one_item(client):
    house, ann, bea, _ = _house(client)
    barrier = threading.Barrier(2)
    ids: list[str] = []

    def add(headers):
        own = TestClient(app)
        barrier.wait()
        ids.append(_add(own, house, headers, "Milk").json()["id"])

    threads = [threading.Thread(target=add, args=(h,)) for h in (ann, bea)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ids)) == 1
    assert [i["name"] for i in _list(client, house, ann)["needed"]] == ["Milk"]


def test_one_trip_marks_several_items_bought(client):
    house, ann, bea, cy = _house(client)
    oil, soap, eggs = (_add(client, house, ann, n).json() for n in ("Oil", "Washing soap", "Eggs"))
    client.post(f"{API}/shopping/{eggs['id']}/bought", headers=cy)  # Cy got the eggs already

    res = client.post(
        f"{API}/households/{house['id']}/shopping/bought",
        json={"item_ids": [oil["id"], soap["id"], eggs["id"]]},
        headers=bea,
    )
    assert res.status_code == 200, res.text
    buyers = {i["name"]: i["bought_by"]["display_name"] for i in res.json()}
    assert buyers == {"Oil": "Bea", "Washing soap": "Bea", "Eggs": "Cy"}  # Cy keeps the eggs
    assert _list(client, house, ann)["needed"] == []
    assert ("shopping_bought", "Oil, Washing soap") in _feed(client, house, ann)


def test_undo_edit_and_remove(client):
    house, ann, bea, cy = _house(client)
    rice = _add(client, house, ann, "Rice").json()
    client.post(f"{API}/shopping/{rice['id']}/bought", headers=bea)

    # Undo: the buyer or whoever added it.
    assert client.post(f"{API}/shopping/{rice['id']}/undo", headers=cy).status_code == 403
    res = client.post(f"{API}/shopping/{rice['id']}/undo", headers=ann)
    assert res.status_code == 200 and res.json()["status"] == "needed"

    res = client.patch(f"{API}/shopping/{rice['id']}", json={"quantity": "5 kg"}, headers=cy)
    assert res.status_code == 200 and res.json()["quantity"] == "5 kg"
    _add(client, house, ann, "Oil")
    res = client.patch(f"{API}/shopping/{rice['id']}", json={"name": "oil"}, headers=cy)
    assert res.status_code == 409

    # Anyone can take a needed item off the list; bought ones stay in the history.
    assert client.delete(f"{API}/shopping/{rice['id']}", headers=cy).status_code == 204
    oil = _list(client, house, ann)["needed"][0]
    client.post(f"{API}/shopping/{oil['id']}/bought", headers=bea)
    assert client.delete(f"{API}/shopping/{oil['id']}", headers=bea).status_code == 400
    res = client.patch(f"{API}/shopping/{oil['id']}", json={"note": "x"}, headers=bea)
    assert res.status_code == 409


def test_other_houses_cant_see_or_touch_the_list(client):
    house, ann, _, _ = _house(client)
    eggs = _add(client, house, ann, "Eggs").json()
    from tests.conftest import register

    dan = register(client, "dan@example.com", "Dan")
    assert client.get(f"{API}/households/{house['id']}/shopping", headers=dan).status_code == 404
    assert client.post(f"{API}/shopping/{eggs['id']}/bought", headers=dan).status_code == 404
