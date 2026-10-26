from tests.conftest import register
from tests.test_chore_api import API


def _setup(client, headers, **body):
    payload = {
        "name": "Maple",
        "address": "1 Maple St",
        "timezone": "UTC",
        "chores": [{"name": "Cooking"}],
        "bills": [{"name": "Rent"}],
        **body,
    }
    return client.post(f"{API}/households/setup", json=payload, headers=headers)


def test_template_has_ten_of_each(client):
    ann = register(client, "ann@example.com", "Ann")
    t = client.get(f"{API}/households/setup/template", headers=ann).json()
    assert t["max_items"] == 10
    assert len(t["chores"]) == len(t["groceries"]) == len(t["bills"]) == 10
    assert t["chores"][0]["name"] == "Cooking" and t["bills"][0]["name"] == "Rent"
    assert {c["key"] for c in t["categories"]} >= {"groceries", "other"}


def test_setup_creates_everything_in_one_go(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    res = _setup(
        client,
        ann,
        roommates=["Bea", "Cy"],
        chores=[
            {"name": "Cooking", "frequency": "daily", "assignment_mode": "rotation"},
            {"name": "Trash", "frequency": "daily", "assignment_mode": "open"},
            {"name": "Bathroom", "frequency": "weekly", "people": ["Cy", "Ann"]},  # Bea's left out
        ],
        groceries=[{"name": "Paneer", "category_key": "groceries"}],
        bills=[
            {"name": "Rent", "payer_mode": "everyone", "amount_cents": 300000},
            {"name": "WiFi", "due_day": 5},
        ],
        currency="inr",
    )
    assert res.status_code == 201, res.text
    house = res.json()
    assert house["my_role"] == "admin" and house["created_by_me"] is True
    hid = house["id"]

    detail = client.get(f"{API}/households/{hid}", headers=ann).json()
    assert [m["display_name"] for m in detail["members"]] == ["Ann", "Bea", "Cy"]

    chores = client.get(f"{API}/households/{hid}/chores", headers=ann).json()
    assert [c["name"] for c in chores] == ["Cooking", "Trash", "Bathroom"]  # no standard chores
    assert [m["display_name"] for m in chores[0]["rotation"]] == ["Ann", "Bea", "Cy"]
    assert [m["display_name"] for m in chores[2]["rotation"]] == ["Cy", "Ann"]

    shopping = client.get(f"{API}/households/{hid}/shopping", headers=ann).json()
    assert [p["name"] for p in shopping["quick_add"]] == ["Paneer"]
    assert len(shopping["categories"]) == 5

    bills = client.get(f"{API}/households/{hid}/bills", headers=ann).json()["bills"]
    assert [b["name"] for b in bills] == ["Rent", "WiFi"]
    assert bills[0]["currency"] == "INR" and bills[0]["current"]["share_cents"] == 100000
    assert bills[1]["payer_mode"] == "anyone"  # the default: one payment settles it

    assert client.get(f"{API}/auth/me", headers=ann).json()["last_household_id"] == hid


def test_nothing_is_saved_when_something_is_wrong(client):
    ann = register(client, "ann@example.com", "Ann")
    # Bills are paid by anyone or split; naming one person who pays is gone.
    res = _setup(client, ann, roommates=["Bea"], bills=[{"name": "WiFi", "payer_mode": "one"}])
    assert res.status_code == 422
    # A roommate with my name, duplicate chores, an unknown category.
    assert _setup(client, ann, roommates=["ann"]).status_code == 400
    assert _setup(client, ann, chores=[{"name": "Cook"}, {"name": "cook"}]).status_code == 422
    assert _setup(client, ann, groceries=[{"name": "Eggs", "category_key": "nope"}]).status_code == 400
    assert _setup(client, ann, chores=[{"name": "Cook", "people": ["Zed"]}]).status_code == 400
    assert _setup(client, ann, chores=[{"name": "Cook", "people": []}]).status_code == 400
    assert client.get(f"{API}/households", headers=ann).json() == []


def test_at_most_ten_of_each(client):
    ann = register(client, "ann@example.com", "Ann")
    too_many = [{"name": f"Chore {i}"} for i in range(11)]
    assert _setup(client, ann, chores=too_many).status_code == 422
    people = [f"P{i}" for i in range(10)]  # 10 roommates + me = 11
    assert _setup(client, ann, roommates=people).status_code == 422
    assert _setup(client, ann, name="Big", roommates=people[:9]).status_code == 201  # 10 people in all


def test_needs_a_chore_and_a_bill_but_people_and_groceries_can_wait(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    assert _setup(client, ann, chores=[]).status_code == 422
    assert _setup(client, ann, bills=[]).status_code == 422
    res = _setup(client, ann, roommates=[], groceries=[])
    assert res.status_code == 201
    detail = client.get(f"{API}/households/{res.json()['id']}", headers=ann).json()
    assert [m["display_name"] for m in detail["members"]] == ["Ann"]  # just me, for now
