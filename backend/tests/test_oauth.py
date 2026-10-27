import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.services import oauth
from app.services.errors import BadRequest
from tests.conftest import sign_up
from tests.test_chore_api import API


@pytest.fixture
def provider(monkeypatch):
    """Stands in for Google / Apple / Facebook: `provider.next = Profile(...)` is what they'll say."""

    class Fake:
        next: oauth.Profile | None = None

    fake = Fake()
    monkeypatch.setattr(oauth, "verify", lambda name, token, nonce=None: fake.next)
    return fake


def _profile(provider="google", subject="g-1", email="ann@example.com", verified=True, first="Ann", last="Lee"):
    return oauth.Profile(provider, subject, email, verified, first, last)


def _oauth(client, name, **body):
    return client.post(f"{API}/auth/oauth/{name}", json={"token": "x" * 40, **body})


def test_google_signs_up_then_signs_in_as_the_same_person(client, provider):
    provider.next = _profile()
    first = _oauth(client, "google").json()
    assert first["access_token"] and first["missing"] == []
    user = first["user"]
    assert (user["email"], user["first_name"], user["email_verified"], user["providers"]) == ("ann@example.com", "Ann", True, ["google"])

    again = _oauth(client, "google").json()
    assert again["user"]["id"] == user["id"]
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {again['access_token']}"})
    assert me.status_code == 200


def test_missing_name_or_contact_is_asked_for_then_the_same_token_finishes(client, provider):
    # Facebook account made with a phone: no email. Apple after the first time: no name.
    provider.next = _profile("facebook", "fb-1", email=None, verified=False, first="", last="")
    res = _oauth(client, "facebook").json()
    assert res["access_token"] is None and res["missing"] == ["name", "contact"]

    done = _oauth(client, "facebook", last_name="Kim", phone="+1 617 555 0100").json()
    assert done["access_token"] and done["user"]["email"] is None and done["user"]["phone"] == "+1 617 555 0100"
    assert done["user"]["name"] == "Kim" and done["user"]["email_verified"] is False

    bad = _oauth(client, "apple", first_name="Bo", phone="not a phone")
    assert bad.status_code == 422


def test_a_verified_provider_email_links_to_the_existing_account(client, provider):
    signed_up = sign_up(client, {"email": "ann@example.com", "first_name": "Ann"})
    provider.next = _profile("apple", "apple-1", email="ANN@example.com", first="", last="")
    res = _oauth(client, "apple").json()
    assert res["user"]["id"] == signed_up["user"]["id"]
    assert res["user"]["providers"] == ["apple", "password"]
    # The password still works too.
    login = client.post(f"{API}/auth/login", json={"email": "ann@example.com", "password": "password123"})
    assert login.status_code == 200


def test_an_unverified_provider_email_never_takes_over_an_account(client, provider):
    sign_up(client, {"email": "ann@example.com", "first_name": "Ann"})
    provider.next = _profile("facebook", "fb-2", email="ann@example.com", verified=False)
    res = _oauth(client, "facebook")
    assert res.status_code == 409 and "already exists" in res.text


def test_social_only_accounts_get_a_helpful_password_error_and_keep_a_contact(client, provider):
    provider.next = _profile("google", "g-9", email="cy@example.com", first="Cy")
    token = _oauth(client, "google").json()["access_token"]
    login = client.post(f"{API}/auth/login", json={"email": "cy@example.com", "password": "whatever1"})
    assert login.status_code == 401 and "Google" in login.text

    headers = {"Authorization": f"Bearer {token}"}
    res = client.patch(f"{API}/auth/me", json={"first_name": "Cy", "phone": "+44 20 7946 0000"}, headers=headers)
    assert res.status_code == 200 and res.json()["phone"] == "+44 20 7946 0000"
    # A name is required: first or last.
    assert client.patch(f"{API}/auth/me", json={"first_name": "", "last_name": ""}, headers=headers).status_code == 422


def test_phone_only_account_must_keep_its_phone(client, provider):
    provider.next = _profile("facebook", "fb-3", email=None, verified=False)
    token = _oauth(client, "facebook", phone="+1 617 555 0199").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.patch(f"{API}/auth/me", json={"first_name": "Ann", "phone": ""}, headers=headers).status_code == 400
    # Adding an email, then the phone can go.
    assert client.patch(f"{API}/auth/me", json={"first_name": "Ann", "email": "ann2@example.com"}, headers=headers).status_code == 200
    assert client.patch(f"{API}/auth/me", json={"first_name": "Ann", "phone": ""}, headers=headers).json()["phone"] is None


def test_unknown_provider_and_buttons_config(client, monkeypatch):
    assert _oauth(client, "instagram").status_code == 404
    monkeypatch.setattr(settings, "google_web_client_id", "web-id")
    monkeypatch.setattr(settings, "facebook_app_id", None)
    config = client.get(f"{API}/auth/providers").json()
    assert config["google"]["web_client_id"] == "web-id" and config["facebook"] is None


def test_id_tokens_are_checked_for_signature_audience_and_nonce(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class Keys:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": key.public_key()})()

    monkeypatch.setitem(oauth._jwks, oauth.APPLE_JWKS, Keys())
    monkeypatch.setattr(settings, "apple_client_ids", "com.shivarv.HouseRoomateManagement")

    def token(aud="com.shivarv.HouseRoomateManagement", nonce="n1", signer=key):
        claims = {"iss": oauth.APPLE_ISSUER, "aud": aud, "sub": "apple-7", "email": "a@privaterelay.appleid.com",
                  "email_verified": "true", "nonce": nonce, "exp": int(time.time()) + 300}
        return jwt.encode(claims, signer, algorithm="RS256")

    profile = oauth.verify("apple", token(), nonce="n1")
    assert (profile.subject, profile.email, profile.email_verified) == ("apple-7", "a@privaterelay.appleid.com", True)
    with pytest.raises(BadRequest):
        oauth.verify("apple", token(aud="someone.else"), nonce="n1")
    with pytest.raises(BadRequest):
        oauth.verify("apple", token(), nonce="other")
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(BadRequest):
        oauth.verify("apple", token(signer=stranger), nonce="n1")
