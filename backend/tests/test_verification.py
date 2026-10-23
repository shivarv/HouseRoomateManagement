import re

from app.core.security import create_email_token
from app.services import email
from tests.test_chore_api import API


def _signup(client, monkeypatch, address="bea@example.com"):
    sent = []
    monkeypatch.setattr(email, "send", lambda to, subject, text: sent.append((to, text)) or True)
    res = client.post(f"{API}/auth/register", json={"email": address, "first_name": "Bea", "password": "password123"})
    assert res.status_code == 201
    return {"Authorization": f"Bearer {res.json()['access_token']}"}, res.json()["user"], sent


def _token(text):
    return re.search(r"verify-email\?token=(\S+)", text).group(1)


def test_sign_up_sends_a_link_that_verifies_the_email(client, monkeypatch):
    headers, user, sent = _signup(client, monkeypatch)
    assert user["email_verified"] is False
    assert sent and sent[0][0] == "bea@example.com"

    res = client.post(f"{API}/auth/verify-email", json={"token": _token(sent[0][1])})  # no sign-in needed
    assert res.status_code == 200 and res.json()["email_verified"] is True
    assert client.get(f"{API}/auth/me", headers=headers).json()["email_verified"] is True
    # Opening the link again is fine; asking for another says it's done.
    assert client.post(f"{API}/auth/verify-email", json={"token": _token(sent[0][1])}).status_code == 200
    again = client.post(f"{API}/auth/me/verification", headers=headers).json()
    assert again["already_verified"] is True and again["sent"] is False


def test_resend_and_bad_links(client, monkeypatch):
    headers, user, sent = _signup(client, monkeypatch)
    res = client.post(f"{API}/auth/me/verification", headers=headers).json()
    assert res == {"sent": True, "email_enabled": email.enabled(), "already_verified": False}
    assert len(sent) == 2

    assert client.post(f"{API}/auth/verify-email", json={"token": "not-a-real-token"}).status_code == 400
    # A link for an address the account no longer has doesn't verify it.
    stale = create_email_token(user["id"], "old@example.com")
    assert client.post(f"{API}/auth/verify-email", json={"token": stale}).status_code == 400
    # A login token isn't a verification link.
    login_token = headers["Authorization"].split()[1]
    assert client.post(f"{API}/auth/verify-email", json={"token": login_token}).status_code == 400
