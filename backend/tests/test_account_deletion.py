from tests.conftest import register
from tests.test_chore_api import API
from tests.test_last_household import _create


def _join(client, headers, house):
    res = client.post(f"{API}/invites/{house['invite_code']}/accept", json={}, headers=headers)
    assert res.status_code == 200, res.text


def test_deleting_my_account_hands_shared_homes_over_and_drops_the_rest(client):
    ann = register(client, "ann@example.com", "Ann")
    bea = register(client, "bea@example.com", "Bea")
    cy = register(client, "cy@example.com", "Cy")
    shared = _create(client, ann, "Maple")
    solo = _create(client, ann, "Cabin")
    _join(client, bea, shared)
    _join(client, cy, shared)

    assert client.delete(f"{API}/auth/me", headers=ann).status_code == 204

    # Signed out everywhere: the account is gone, and so is the email for logging in.
    assert client.get(f"{API}/auth/me", headers=ann).status_code == 401
    res = client.post(f"{API}/auth/login", json={"email": "ann@example.com", "password": "password123"})
    assert res.status_code == 401

    # Bea joined first, so she runs Maple now; Ann's spot stays by name, without her account.
    detail = client.get(f"{API}/households/{shared['id']}", headers=bea).json()
    roles = {m["display_name"]: m["role"] for m in detail["members"]}
    assert roles["Bea"] == "admin" and roles["Cy"] == "member"
    assert "Ann" not in roles  # no longer an active member
    actions = [e["action"] for e in client.get(f"{API}/households/{shared['id']}/activity", headers=bea).json()]
    assert "member_left" in actions and "member_made_admin" in actions

    # Ann was alone in the cabin: it went with her account.
    assert client.get(f"{API}/households/{solo['id']}", headers=bea).status_code in (403, 404)

    # The email is free again.
    register(client, "ann@example.com", "Ann")


def test_another_admin_keeps_running_the_house(client):
    ann = register(client, "ann@example.com", "Ann")
    bea = register(client, "bea@example.com", "Bea")
    house = _create(client, ann, "Maple")
    _join(client, bea, house)
    bea_id = next(m["id"] for m in client.get(f"{API}/households/{house['id']}", headers=ann).json()["members"] if m["display_name"] == "Bea")
    client.patch(f"{API}/members/{bea_id}", json={"role": "admin"}, headers=ann)

    assert client.delete(f"{API}/auth/me", headers=bea).status_code == 204
    actions = [e["action"] for e in client.get(f"{API}/households/{house['id']}/activity", headers=ann).json()]
    assert "member_made_admin" not in actions
