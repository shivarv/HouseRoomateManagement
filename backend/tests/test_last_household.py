
from tests.conftest import register, sign_up
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


def test_invite_links_show_the_house_before_signing_in(client):
    ann = register(client, "ann@example.com", "Ann")
    maple = _create(client, ann, "Maple")
    res = client.get(f"{API}/invites/{maple['invite_code'].lower()}/public")  # no token
    assert res.status_code == 200 and res.json() == {"household_name": "Maple", "people": 1}
    assert client.get(f"{API}/invites/NOPE1234/public").status_code == 404
    assert client.get(f"{API}/invites/{maple['invite_code']}").status_code == 401  # names need sign-in


def test_first_and_last_names(client):
    res = sign_up(client, {"email": "bea@example.com", "first_name": " Beatrice ", "last_name": "Smith"})
    user = res["user"]
    assert (user["first_name"], user["last_name"], user["name"]) == ("Beatrice", "Smith", "Beatrice Smith")
    bea = {"Authorization": f"Bearer {res['access_token']}"}
    # Older clients send one name: it's split.
    old = sign_up(client, {"email": "cy@example.com", "name": "Cy Van Dyke"})
    assert (old["user"]["first_name"], old["user"]["last_name"]) == ("Cy", "Van Dyke")
    assert client.post(f"{API}/auth/register", json={"email": "x@example.com", "password": "password123"}).status_code == 422

    house = _create(client, bea, "Maple")
    # Renaming myself: houses that use my old full name follow it.
    res = client.patch(f"{API}/auth/me", json={"first_name": "Bea", "last_name": "Smith"}, headers=bea)
    assert res.status_code == 200 and res.json()["name"] == "Bea Smith"
    members = client.get(f"{API}/households/{house['id']}", headers=bea).json()["members"]
    assert (members[0]["display_name"], members[0]["first_name"], members[0]["last_name"]) == ("Bea Smith", "Bea", "Smith")


def test_members_have_status_email_and_phone(client, monkeypatch):
    from app.services import email

    monkeypatch.setattr(email, "deliver", lambda *a: email.NOT_SET_UP)
    ann = register(client, "ann@example.com", "Ann")
    house = _create(client, ann, "Maple")
    # A name alone isn't enough: they need an email or phone to be invited.
    assert client.post(f"{API}/households/{house['id']}/members", json={"display_name": "Bea"}, headers=ann).status_code == 422
    res = client.post(f"{API}/households/{house['id']}/members", json={"display_name": "Bea", "phone": "+1 617 555 0199"}, headers=ann)
    assert res.status_code == 201
    bea = res.json()["member"]
    assert bea["status"] == "added" and bea["email"] is None
    assert res.json()["link"].endswith(f"/join/{house['invite_code']}?as={bea['id']}") and res.json()["emailed"] is False

    res = client.patch(f"{API}/members/{bea['id']}", json={"email": "Bea@Example.com", "phone": "+1 617 555 0100"}, headers=ann)
    assert res.status_code == 200 and res.json()["email"] == "bea@example.com" and res.json()["phone"] == "+1 617 555 0100"
    assert client.patch(f"{API}/members/{bea['id']}", json={"phone": "call me"}, headers=ann).status_code == 422

    client.post(f"{API}/households/{house['id']}/email-invites", json={"emails": ["bea@example.com"]}, headers=ann)
    members = {m["display_name"]: m for m in client.get(f"{API}/households/{house['id']}", headers=ann).json()["members"]}
    assert members["Ann"]["status"] == "verified" and members["Ann"]["email"] == "ann@example.com"
    assert members["Bea"]["status"] == "invited"

    # Bea signs up with that email and joins with the plain link: she's matched to "Bea".
    bea_user = register(client, "bea@example.com", "Beatrice")
    client.post(f"{API}/invites/{house['invite_code']}/accept", json={}, headers=bea_user)
    members = client.get(f"{API}/households/{house['id']}", headers=ann).json()["members"]
    assert [(m["display_name"], m["status"]) for m in members] == [("Ann", "verified"), ("Bea", "verified")]
    me = next(m for m in members if m["display_name"] == "Bea")
    assert client.patch(f"{API}/members/{me['id']}", json={"email": "x@y.co"}, headers=ann).status_code == 400
