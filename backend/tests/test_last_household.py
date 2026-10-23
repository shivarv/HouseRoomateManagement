from tests.conftest import register
from tests.test_chore_api import API


def _me(client, headers):
    res = client.get(f"{API}/auth/me", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _create(client, headers, name):
    res = client.post(f"{API}/households", json={"name": name, "address": f"1 {name} Rd", "timezone": "UTC"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _pick(client, headers, household_id):
    return client.put(
        f"{API}/auth/me/last-household", json={"household_id": household_id}, headers=headers
    )


def test_last_household_follows_create_join_and_switch(client):
    ann = register(client, "ann@example.com", "Ann")
    assert _me(client, ann)["last_household_id"] is None

    maple = _create(client, ann, "Maple")
    assert _me(client, ann)["last_household_id"] == maple["id"]
    oak = _create(client, ann, "Oak")
    assert _me(client, ann)["last_household_id"] == oak["id"]

    res = _pick(client, ann, maple["id"])
    assert res.status_code == 200 and res.json()["last_household_id"] == maple["id"]
    assert _me(client, ann)["last_household_id"] == maple["id"]

    # Joining a house makes it the one I land on.
    bea = register(client, "bea@example.com", "Bea")
    client.post(f"{API}/invites/{oak['invite_code']}/accept", json={}, headers=bea)
    assert _me(client, bea)["last_household_id"] == oak["id"]


def test_cannot_pick_a_house_im_not_in(client):
    ann = register(client, "ann@example.com", "Ann")
    maple = _create(client, ann, "Maple")
    bea = register(client, "bea@example.com", "Bea")
    assert _pick(client, bea, maple["id"]).status_code == 404
    assert _me(client, bea)["last_household_id"] is None


def test_house_names_are_unique_per_creator(client):
    ann = register(client, "ann@example.com", "Ann")
    maple = _create(client, ann, "Maple")
    assert maple["address"] == "1 Maple Rd" and maple["created_by_me"] is True

    # Same creator, same name (any case or spacing): refused.
    res = client.post(
        f"{API}/households", json={"name": "  maple ", "address": "2 Other Rd"}, headers=ann
    )
    assert res.status_code == 409

    # Someone else can have their own "Maple"; joining Ann's doesn't make it theirs.
    bea = register(client, "bea@example.com", "Bea")
    assert _create(client, bea, "Maple")["created_by_me"] is True
    client.post(f"{API}/invites/{maple['invite_code']}/accept", json={}, headers=bea)
    joined = next(h for h in client.get(f"{API}/households", headers=bea).json() if h["id"] == maple["id"])
    assert joined["created_by_me"] is False

    # Renaming into a clash with another of the creator's houses is refused too.
    oak = _create(client, ann, "Oak")
    res = client.patch(f"{API}/households/{oak['id']}", json={"name": "MAPLE"}, headers=ann)
    assert res.status_code == 409
    res = client.patch(
        f"{API}/households/{oak['id']}", json={"name": "Oak", "address": "9 Oak Ave"}, headers=ann
    )
    assert res.status_code == 200 and res.json()["address"] == "9 Oak Ave"


def test_address_is_required(client):
    ann = register(client, "ann@example.com", "Ann")
    assert client.post(f"{API}/households", json={"name": "Maple"}, headers=ann).status_code == 422
    res = client.post(f"{API}/households", json={"name": "Maple", "address": "   "}, headers=ann)
    assert res.status_code == 400


def test_admins_delete_homes_but_not_their_last_one(client, fake_today):
    ann = register(client, "ann@example.com", "Ann")
    maple = _create(client, ann, "Maple")
    # Only one home Ann runs: it can't go.
    res = client.delete(f"{API}/households/{maple['id']}", headers=ann)
    assert res.status_code == 409 and "last home" in res.text

    oak = _create(client, ann, "Oak")
    bea = register(client, "bea@example.com", "Bea")
    client.post(f"{API}/invites/{oak['invite_code']}/accept", json={}, headers=bea)
    assert client.delete(f"{API}/households/{oak['id']}", headers=bea).status_code == 403  # not an admin

    assert client.delete(f"{API}/households/{oak['id']}", headers=ann).status_code == 204
    assert [h["name"] for h in client.get(f"{API}/households", headers=ann).json()] == ["Maple"]
    assert client.get(f"{API}/households", headers=bea).json() == []  # gone for everyone
    assert _me(client, ann)["last_household_id"] is None  # Oak was the one she'd opened last
    # Maple is the last one again.
    assert client.delete(f"{API}/households/{maple['id']}", headers=ann).status_code == 409
