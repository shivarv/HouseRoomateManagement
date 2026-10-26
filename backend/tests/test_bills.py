from datetime import date

from tests.test_chore_api import API
from tests.test_help import _house

# fake_today: Monday, Oct 19 2026.


def _bills(client, house, headers, **params):
    res = client.get(f"{API}/households/{house['id']}/bills", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return {b["name"]: b for b in res.json()["bills"]}


def _create(client, house, headers, **body):
    return client.post(f"{API}/households/{house['id']}/bills", json=body, headers=headers)


def _member_id(client, house, headers, name):
    detail = client.get(f"{API}/households/{house['id']}", headers=headers).json()
    return next(m["id"] for m in detail["members"] if m["display_name"] == name)


def _pay(client, bill, headers, **body):
    return client.post(f"{API}/bills/{bill['id']}/pay", json=body, headers=headers)


def test_new_houses_get_four_monthly_bills_due_on_the_first(client, fake_today):
    house, ann, bea, _ = _house(client)
    bills = _bills(client, house, bea)
    assert list(bills) == ["Rent", "Electricity", "WiFi", "Gas"]
    assert {b["frequency"] for b in bills.values()} == {"monthly"}
    assert {b["due_day"] for b in bills.values()} == {1}
    assert bills["Rent"]["payer_mode"] == "everyone" and bills["Rent"]["amount_type"] == "fixed"
    assert bills["Gas"]["amount_type"] == "variable"
    rent = bills["Rent"]["current"]
    assert rent["period"] == "2026-10-01" and rent["label"] == "Oct 2026" and rent["status"] == "overdue"

    # Admins edit them.
    wifi = bills["WiFi"]
    assert client.patch(f"{API}/bills/{wifi['id']}", json={"amount_cents": 6000}, headers=bea).status_code == 403
    res = client.patch(f"{API}/bills/{wifi['id']}", json={"amount_cents": 6000, "due_day": 25}, headers=ann)
    assert res.status_code == 200
    assert res.json()["current"]["amount_cents"] == 6000 and res.json()["current"]["due_date"] == "2026-10-25"
    assert res.json()["current"]["status"] == "upcoming"

    assert client.delete(f"{API}/bills/{bills['Gas']['id']}", headers=ann).status_code == 204
    assert "Gas" not in _bills(client, house, bea)


def test_only_admins_set_up_bills_paid_by_anyone_or_split(client, fake_today):
    house, ann, bea, _ = _house(client)
    assert _create(client, house, bea, name="Cleaner").status_code == 403
    assert _create(client, house, ann, name="Cleaner", payer_mode="one").status_code == 422
    res = _create(client, house, ann, name="Cleaner", amount_cents=2500)
    assert res.status_code == 201 and res.json()["payer_mode"] == "anyone"
    assert "payer" not in res.json()

    cleaner = res.json()
    client.patch(f"{API}/bills/{cleaner['id']}", json={"is_active": False}, headers=ann)
    assert "Cleaner" not in _bills(client, house, bea)
    assert "Cleaner" in _bills(client, house, ann, include_paused=True)
    assert _pay(client, cleaner, bea).status_code == 400


def test_anyone_mode_first_payer_wins_and_undo(client, fake_today):
    house, ann, bea, cy = _house(client)
    power = _bills(client, house, bea)["Electricity"]
    assert _pay(client, power, bea).status_code == 201
    again = _pay(client, power, cy)
    assert again.status_code == 409 and "Bea already paid it" in again.text

    current = _bills(client, house, cy)["Electricity"]["current"]
    assert current["status"] == "paid" and current["payments"][0]["can_undo"] is False
    payment_id = current["payments"][0]["id"]
    assert client.delete(f"{API}/bill-payments/{payment_id}", headers=cy).status_code == 403
    assert client.delete(f"{API}/bill-payments/{payment_id}", headers=bea).status_code == 204

    feed = client.get(f"{API}/households/{house['id']}/activity", headers=ann).json()
    details = [(e["action"], e["detail"]) for e in feed if e["action"].startswith("bill_")]
    assert ("bill_paid", "Electricity · Oct 2026") in details
    assert ("bill_unpaid", "Electricity · Oct 2026") in details


def test_everyone_mode_counts_each_person_and_splits_the_amount(client, fake_today):
    house, ann, bea, cy = _house(client)
    rent = _bills(client, house, ann)["Rent"]
    client.patch(f"{API}/bills/{rent['id']}", json={"amount_cents": 400000}, headers=ann)
    current = _bills(client, house, bea)["Rent"]["current"]
    assert current["expected_count"] == 8 and current["share_cents"] == 50000  # $4,000 / 8

    _pay(client, rent, bea)
    assert _pay(client, rent, bea).status_code == 409  # once per person
    cy_id = _member_id(client, house, ann, "Cy")
    assert _pay(client, rent, ann, member_id=cy_id).status_code == 201  # marking for someone
    current = _bills(client, house, bea)["Rent"]["current"]
    assert current["paid_count"] == 2 and current["i_paid"] is True and current["status"] == "overdue"

    detail = client.get(f"{API}/households/{house['id']}", headers=ann).json()
    paid = {p["member"]["id"] for p in current["payments"]}
    for member in detail["members"]:
        if member["id"] not in paid:
            _pay(client, rent, ann, member_id=member["id"])
    assert _bills(client, house, bea)["Rent"]["current"]["status"] == "paid"


def test_variable_bills_get_each_periods_amount_from_an_admin(client, fake_today):
    house, ann, bea, _ = _house(client)
    gas = _bills(client, house, ann)["Gas"]
    assert gas["current"]["amount_cents"] is None and gas["last_amount_cents"] is None

    assert client.put(f"{API}/bills/{gas['id']}/amount", json={"amount_cents": 4200}, headers=bea).status_code == 403
    res = client.put(f"{API}/bills/{gas['id']}/amount", json={"amount_cents": 4200}, headers=ann)
    assert res.status_code == 200 and res.json()["current"]["amount_cents"] == 4200
    # September's bill, set late; future months can't be set.
    res = client.put(
        f"{API}/bills/{gas['id']}/amount", json={"amount_cents": 3900, "period": "2026-09-14"}, headers=ann
    )
    assert res.status_code == 200
    future = client.put(
        f"{API}/bills/{gas['id']}/amount", json={"amount_cents": 1, "period": "2026-11-01"}, headers=ann
    )
    assert future.status_code == 400

    wifi = _bills(client, house, ann)["WiFi"]
    fixed = client.put(f"{API}/bills/{wifi['id']}/amount", json={"amount_cents": 1}, headers=ann)
    assert fixed.status_code == 400  # fixed bills change in their settings

    # Next month starts with no amount, showing last month's as a hint.
    fake_today.today = date(2026, 11, 3)
    gas = _bills(client, house, bea)["Gas"]
    assert gas["current"]["amount_cents"] is None and gas["last_amount_cents"] == 4200
    history = client.get(f"{API}/bills/{gas['id']}/history", params={"limit": 2}, headers=bea).json()
    assert [(h["label"], h["amount_cents"]) for h in history] == [("Oct 2026", 4200), ("Sep 2026", 3900)]


def test_weekly_and_daily_bills_start_fresh_each_period(client, fake_today):
    house, ann, bea, _ = _house(client)
    bad = _create(client, house, ann, name="Cleaner", frequency="weekly", due_day=9)
    assert bad.status_code == 422  # weekdays are 1–7
    cleaner = _create(client, house, ann, name="Cleaner", frequency="weekly", due_day=5).json()
    milk = _create(client, house, ann, name="Milk money", frequency="daily").json()
    assert cleaner["current"]["label"] == "Week of Oct 19" and cleaner["current"]["due_date"] == "2026-10-23"
    assert cleaner["current"]["status"] == "upcoming"  # Friday, 4 days away
    assert milk["current"]["label"] == "Mon, Oct 19" and milk["current"]["status"] == "due"

    _pay(client, milk, bea)
    _pay(client, cleaner, bea)
    assert _bills(client, house, bea)["Milk money"]["current"]["status"] == "paid"

    # A day later: the daily one is due again; the weekly one is still paid for this week.
    fake_today.today = date(2026, 10, 20)
    bills = _bills(client, house, bea)
    assert bills["Milk money"]["current"]["status"] == "due"
    assert bills["Milk money"]["current"]["period"] == "2026-10-20"
    assert bills["Cleaner"]["current"]["status"] == "paid"
    history = client.get(f"{API}/bills/{milk['id']}/history", params={"limit": 1}, headers=bea).json()
    assert history[0]["label"] == "Mon, Oct 19" and history[0]["status"] == "paid"

    # Next week: the weekly one starts fresh. Future periods can't be paid.
    fake_today.today = date(2026, 10, 26)
    assert _bills(client, house, bea)["Cleaner"]["current"]["status"] == "upcoming"
    assert _pay(client, cleaner, bea, period="2026-11-02").status_code == 400

    # Switching a monthly bill (due the 1st) to weekly keeps a valid weekday.
    rent = _bills(client, house, ann)["Rent"]
    client.patch(f"{API}/bills/{rent['id']}", json={"due_day": 15}, headers=ann)
    res = client.patch(f"{API}/bills/{rent['id']}", json={"frequency": "weekly"}, headers=ann)
    assert res.status_code == 200 and res.json()["due_day"] == 1
