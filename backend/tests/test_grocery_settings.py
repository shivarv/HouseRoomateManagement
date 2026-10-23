from tests.test_chore_api import API
from tests.test_help import _house
from tests.test_shopping import _add, _list


def _settings(client, house, headers):
    res = client.get(f"{API}/households/{house['id']}/grocery-settings", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_new_house_has_the_standard_lists_and_only_admins_configure_them(client):
    house, ann, bea, _ = _house(client)
    listing = _list(client, house, bea)
    assert [c["key"] for c in listing["categories"]] == [
        "groceries", "toiletries", "cleaning", "household", "other",
    ]
    assert [p["name"] for p in listing["quick_add"]][:3] == ["Bread", "Dish soap", "Eggs"]  # alphabetical
    assert next(c for c in listing["categories"] if c["key"] == "other")["can_delete"] is False

    assert client.get(f"{API}/households/{house['id']}/grocery-settings", headers=bea).status_code == 403
    res = client.post(f"{API}/households/{house['id']}/grocery-presets", json={"name": "Paneer"}, headers=bea)
    assert res.status_code == 403
    assert len(_settings(client, house, ann)["presets"]) == 15


def test_categories_add_rename_reorder_and_delete_moves_items_to_other(client):
    house, ann, bea, _ = _house(client)
    res = client.post(
        f"{API}/households/{house['id']}/grocery-categories",
        json={"label": "Snacks", "icon": "🍿"},
        headers=ann,
    )
    assert res.status_code == 201
    snacks = res.json()
    assert snacks["key"] == "snacks" and snacks["position"] == 5

    # Same label (any case) is refused; unknown categories can't be used for items.
    again = client.post(f"{API}/households/{house['id']}/grocery-categories", json={"label": "snacks"}, headers=ann)
    assert again.status_code == 409
    assert _add(client, house, bea, "Chips", category="nope").status_code == 400

    chips = _add(client, house, bea, "Chips", category="snacks").json()
    assert chips["category"] == "snacks"
    preset = client.post(
        f"{API}/households/{house['id']}/grocery-presets",
        json={"name": "Popcorn", "category_key": "snacks"},
        headers=ann,
    ).json()

    res = client.patch(f"{API}/grocery-categories/{snacks['id']}", json={"label": "Munchies"}, headers=ann)
    assert res.status_code == 200 and res.json()["key"] == "snacks"  # the key never changes

    ids = [c["id"] for c in _settings(client, house, ann)["categories"]]
    res = client.put(
        f"{API}/households/{house['id']}/grocery-categories/order",
        json={"ids": [ids[-1], *ids[:-1]]},
        headers=ann,
    )
    assert res.status_code == 204
    assert _list(client, house, bea)["categories"][0]["label"] == "Munchies"
    bad = client.put(f"{API}/households/{house['id']}/grocery-categories/order", json={"ids": ids[:2]}, headers=ann)
    assert bad.status_code == 400

    other = next(c for c in _settings(client, house, ann)["categories"] if c["key"] == "other")
    assert client.delete(f"{API}/grocery-categories/{other['id']}", headers=ann).status_code == 400
    assert client.delete(f"{API}/grocery-categories/{snacks['id']}", headers=ann).status_code == 204
    listing = _list(client, house, bea)
    assert next(i for i in listing["needed"] if i["id"] == chips["id"])["category"] == "other"
    assert next(p for p in listing["quick_add"] if p["id"] == preset["id"])["category_key"] == "other"


def test_new_items_become_suggestions_the_admin_adds_or_dismisses(client):
    house, ann, bea, cy = _house(client)
    paneer = _add(client, house, bea, "Paneer").json()
    client.post(f"{API}/shopping/{paneer['id']}/bought", headers=cy)
    _add(client, house, cy, "paneer")  # bought, then needed again: added twice
    _add(client, house, bea, "Coriander")
    _add(client, house, bea, "Eggs")  # already a quick-add item: not a suggestion

    suggestions = _settings(client, house, ann)["suggestions"]
    assert [(s["name"], s["times_added"]) for s in suggestions] == [("paneer", 2), ("Coriander", 1)]
    assert suggestions[0]["category_key"] == "groceries"

    # Accept one: it becomes a quick-add chip for everyone and stops being suggested.
    res = client.post(
        f"{API}/households/{house['id']}/grocery-presets",
        json={"name": "Paneer", "category_key": "groceries"},
        headers=ann,
    )
    assert res.status_code == 201
    assert "Paneer" in [p["name"] for p in _list(client, house, bea)["quick_add"]]
    dup = client.post(f"{API}/households/{house['id']}/grocery-presets", json={"name": "PANEER"}, headers=ann)
    assert dup.status_code == 409

    # Dismiss the other: gone from suggestions, but can still be added later.
    res = client.post(
        f"{API}/households/{house['id']}/grocery-suggestions/dismiss", json={"name": "Coriander"}, headers=ann
    )
    assert res.status_code == 204
    assert _settings(client, house, ann)["suggestions"] == []

    # Quick-add items now decide the category of items added by name.
    assert _add(client, house, bea, "Paneer").json()["category"] == "groceries"


def test_removing_and_restoring_standard_items(client):
    house, ann, bea, _ = _house(client)
    eggs = next(p for p in _settings(client, house, ann)["presets"] if p["name"] == "Eggs")
    assert client.delete(f"{API}/grocery-presets/{eggs['id']}", headers=ann).status_code == 204

    # The house bought eggs before: removing the chip must not bring it back as a suggestion.
    item = _add(client, house, bea, "Eggs").json()
    client.post(f"{API}/shopping/{item['id']}/bought", headers=bea)
    settings = _settings(client, house, ann)
    assert "Eggs" not in [p["name"] for p in settings["presets"]]
    assert settings["suggestions"] == []

    renamed = next(p for p in settings["presets"] if p["name"] == "Milk")
    res = client.patch(
        f"{API}/grocery-presets/{renamed['id']}", json={"name": "Oat milk"}, headers=ann
    )
    assert res.status_code == 200

    res = client.post(f"{API}/households/{house['id']}/grocery-settings/restore", headers=ann)
    assert res.status_code == 200
    names = [p["name"] for p in res.json()["presets"]]
    assert "Eggs" in names and "Oat milk" in names and "Milk" in names
    assert len(names) == 16  # the 15 standard ones plus the renamed one
