import re

from app.core.security import create_email_token
from app.services import email
from tests.conftest import register
from tests.test_chore_api import API


def _capture(monkeypatch):
    sent = []
    monkeypatch.setattr(email, "deliver", lambda to, subject, text: sent.append((to, subject, text)))  # None: sent
    return sent


def _signup(client, address="bea@example.com", **extra):
    body = {"email": address, "first_name": "Bea", "password": "password123", **extra}
    return client.post(f"{API}/auth/register", json=body)


def _login(client, address="bea@example.com"):
    return client.post(f"{API}/auth/login", json={"email": address, "password": "password123"})


def _link(text):
    return re.search(r"verify-email\?token=(\S+)", text).group(0)


def _token(text):
    return re.search(r"token=([^&\s]+)", text).group(1)


def test_no_sign_in_until_the_emailed_link_is_opened(client, monkeypatch):
    sent = _capture(monkeypatch)
    res = _signup(client, next="/join/ABCD1234")
    assert res.status_code == 201 and "access_token" not in res.json()
    assert res.json()["email"] == "bea@example.com" and res.json()["sent"] is True
    to, subject, text = sent[0]
    assert to == "bea@example.com" and "Confirm your email" in subject
    assert _link(text).endswith("&next=/join/ABCD1234")  # lands back on the invite

    assert _login(client).status_code == 403  # right password, email not confirmed

    # The first open confirms and signs in.
    first = client.post(f"{API}/auth/verify-email", json={"token": _token(text)})
    assert first.status_code == 200 and first.json()["user"]["email_verified"] is True
    headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 200
    # Opening it again only confirms: a forwarded email can't be used to get in.
    again = client.post(f"{API}/auth/verify-email", json={"token": _token(text)})
    assert again.status_code == 200 and again.json()["access_token"] is None
    assert _login(client).status_code == 200


def test_resend_works_signed_out_and_says_nothing_about_accounts(client, monkeypatch):
    sent = _capture(monkeypatch)
    _signup(client)
    res = client.post(f"{API}/auth/resend-verification", json={"email": "Bea@Example.com", "next": "/join/X"})
    assert res.status_code == 200 and len(sent) == 2 and "next=/join/X" in sent[1][2]
    nobody = client.post(f"{API}/auth/resend-verification", json={"email": "nobody@example.com"})
    assert nobody.status_code == 200 and nobody.json() == res.json() and len(sent) == 2
    # Only paths on our own site.
    bad = client.post(f"{API}/auth/resend-verification", json={"email": "bea@example.com", "next": "//evil.com"})
    assert bad.status_code == 422


def test_bad_links(client, monkeypatch):
    _capture(monkeypatch)
    _signup(client)
    assert client.post(f"{API}/auth/verify-email", json={"token": "not-a-real-token"}).status_code == 400
    # A link for an address the account no longer has doesn't verify it.
    from app.db.session import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        user_id = db.query(User.id).filter(User.email == "bea@example.com").scalar()
    stale = create_email_token(user_id, "old@example.com")
    assert client.post(f"{API}/auth/verify-email", json={"token": stale}).status_code == 400
    # A sign-in token isn't a verification link.
    ann = register(client, "ann@example.com", "Ann")
    assert client.post(f"{API}/auth/verify-email", json={"token": ann["Authorization"].split()[1]}).status_code == 400


def test_only_verified_people_can_be_admins_and_an_email_gets_the_invite(client, monkeypatch):
    sent = _capture(monkeypatch)
    ann = register(client, "ann@example.com", "Ann")
    house = client.post(f"{API}/households", json={"name": "Maple", "address": "1 Maple Rd"}, headers=ann).json()
    res = client.post(f"{API}/households/{house['id']}/members", json={"display_name": "Bea", "email": "Bea@Example.com"}, headers=ann)
    assert res.status_code == 201 and res.json()["emailed"] is True
    bea = res.json()["member"]
    assert bea["status"] == "invited" and bea["email"] == "bea@example.com"
    assert any(to == "bea@example.com" and "/invite/" in text for to, _, text in sent)
    # The same email twice is refused.
    dup = client.post(f"{API}/households/{house['id']}/members", json={"display_name": "B", "email": "bea@example.com"}, headers=ann)
    assert dup.status_code == 409
    # Not signed up yet: can't be made admin, and can't be left without an email or phone.
    assert client.patch(f"{API}/members/{bea['id']}", json={"role": "admin"}, headers=ann).status_code == 400
    assert client.patch(f"{API}/members/{bea['id']}", json={"email": ""}, headers=ann).status_code == 400

    # Once she has signed up (confirmed) and joined, she can be.
    bea_headers = register(client, "bea@example.com", "Bea")
    client.post(f"{API}/invites/{house['invite_code']}/accept", json={}, headers=bea_headers)
    assert client.patch(f"{API}/members/{bea['id']}", json={"role": "admin"}, headers=ann).json()["role"] == "admin"


def test_resend_request_has_a_user_agent_and_errors_are_logged(monkeypatch, caplog):
    import io
    import urllib.error
    import urllib.request

    from app.core.config import settings

    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(settings, "brevo_api_key", None)
    seen = {}

    def refuse(request, timeout):
        seen["agent"] = request.get_header("User-agent")
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"message":"domain not verified"}')
        )

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert email.send("bea@example.com", "Hi", "text") is False
    assert seen["agent"] and "Python-urllib" not in seen["agent"]
    assert "403" in caplog.text and "domain not verified" in caplog.text


def test_brevo_is_used_when_its_key_is_set(monkeypatch, caplog):
    import io
    import json
    import urllib.error
    import urllib.request

    from app.core.config import settings

    monkeypatch.setattr(settings, "brevo_api_key", "xkeysib-test")
    monkeypatch.setattr(settings, "resend_api_key", "re_test")  # Brevo wins
    monkeypatch.setattr(settings, "email_from", "Roommates <invites@housematemanagement.com>")
    seen = {}

    class Ok:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def capture(request, timeout):
        seen.update(
            url=request.full_url, key=request.get_header("Api-key"), body=json.loads(request.data)
        )
        return Ok()

    monkeypatch.setattr(urllib.request, "urlopen", capture)
    assert email.send("bea@example.com", "Hi", "text") is True
    assert seen["url"] == email.BREVO_URL and seen["key"] == "xkeysib-test"
    assert seen["body"]["sender"] == {
        "name": "Roommates",
        "email": "invites@housematemanagement.com",
    }
    assert (
        seen["body"]["to"] == [{"email": "bea@example.com"}]
        and seen["body"]["textContent"] == "text"
    )

    def refuse(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 400, "Bad", {}, io.BytesIO(b'{"message":"sender not valid"}')
        )

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert email.send("bea@example.com", "Hi", "text") is False
    assert "Brevo 400" in caplog.text and "sender not valid" in caplog.text
