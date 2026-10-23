"""Private invite links: they work only while the invite is pending, unexpired, and for that email."""

import re
from datetime import UTC, datetime, timedelta

from app.services import email
from tests.conftest import register
from tests.test_chore_api import API
from tests.test_last_household import _create


def _invite(client, monkeypatch, headers, house, address="bea@example.com"):
    sent = []
    monkeypatch.setattr(email, "deliver", lambda to, subject, text: sent.append(text))  # None: sent
    res = client.post(f"{API}/households/{house['id']}/email-invites", json={"emails": [address]}, headers=headers)
    assert res.status_code == 200, res.text
    return re.search(r"/invite/(\S+)", sent[-1]).group(1), sent[-1]


def _expired(res):
    return res.status_code == 404 and "expired or was cancelled" in res.json()["detail"]


def test_the_email_has_a_private_link_that_joins_once(client, monkeypatch):
    ann = register(client, "ann@example.com", "Ann")
    house = _create(client, ann, "Maple")
    token, text = _invite(client, monkeypatch, ann, house)
    assert house["invite_code"] not in text  # the house code isn't in the email

    page = client.get(f"{API}/invite-links/{token}")  # no sign-in needed
    assert page.status_code == 200 and page.json() == {"household_name": "Maple", "people": 1, "email": "bea@example.com"}

    bea = register(client, "bea@example.com", "Bea")
    joined = client.post(f"{API}/invite-links/{token}/accept", headers=bea)
    assert joined.status_code == 200 and joined.json()["id"] == house["id"]
    # Used up: the link now says expired, for anyone.
    assert _expired(client.get(f"{API}/invite-links/{token}"))


def test_cancelled_resent_expired_or_made_up_links_dont_work(client, monkeypatch):
    from app.db.session import SessionLocal
    from app.models import HouseholdInvite

    ann = register(client, "ann@example.com", "Ann")
    house = _create(client, ann, "Maple")
    bea = register(client, "bea@example.com", "Bea")

    # Cancelled after she opened it, before she joined: the join is refused.
    token, _ = _invite(client, monkeypatch, ann, house)
    assert client.get(f"{API}/invite-links/{token}").status_code == 200
    invite_id = client.get(f"{API}/households/{house['id']}/email-invites", headers=ann).json()[0]["id"]
    assert client.delete(f"{API}/email-invites/{invite_id}", headers=ann).status_code == 204
    assert _expired(client.get(f"{API}/invite-links/{token}"))
    assert _expired(client.post(f"{API}/invite-links/{token}/accept", headers=bea))

    # Sending it again makes a new link; the old one stays dead.
    old, _ = _invite(client, monkeypatch, ann, house)
    new, _ = _invite(client, monkeypatch, ann, house)
    assert old != new and _expired(client.get(f"{API}/invite-links/{old}"))

    # Past its week: expired.
    with SessionLocal() as db:
        db.query(HouseholdInvite).update({HouseholdInvite.expires_at: datetime.now(UTC) - timedelta(minutes=1)})
        db.commit()
    assert _expired(client.post(f"{API}/invite-links/{new}/accept", headers=bea))
    assert client.get(f"{API}/me/invites", headers=bea).json() == []  # not offered on her welcome screen either

    assert _expired(client.get(f"{API}/invite-links/made-up-token"))
    members = client.get(f"{API}/households/{house['id']}", headers=ann).json()["members"]
    assert [m["display_name"] for m in members] == ["Ann"]


def test_a_forwarded_link_only_works_for_the_invited_email(client, monkeypatch):
    ann = register(client, "ann@example.com", "Ann")
    house = _create(client, ann, "Maple")
    token, _ = _invite(client, monkeypatch, ann, house)
    cy = register(client, "cy@example.com", "Cy")
    assert _expired(client.post(f"{API}/invite-links/{token}/accept", headers=cy))
    # Bea can still use it.
    bea = register(client, "bea@example.com", "Bea")
    assert client.post(f"{API}/invite-links/{token}/accept", headers=bea).status_code == 200


def test_admins_reset_the_shared_link(client):
    ann = register(client, "ann@example.com", "Ann")
    house = _create(client, ann, "Maple")
    bea = register(client, "bea@example.com", "Bea")
    client.post(f"{API}/invites/{house['invite_code']}/accept", json={}, headers=bea)
    assert client.post(f"{API}/households/{house['id']}/invite-code", headers=bea).status_code == 403

    res = client.post(f"{API}/households/{house['id']}/invite-code", headers=ann)
    assert res.status_code == 200 and res.json()["invite_code"] != house["invite_code"]
    cy = register(client, "cy@example.com", "Cy")
    assert client.post(f"{API}/invites/{house['invite_code']}/accept", json={}, headers=cy).status_code == 404
    assert client.post(f"{API}/invites/{res.json()['invite_code']}/accept", json={}, headers=cy).status_code == 200


def test_a_failed_email_says_why(client, monkeypatch):
    ann = register(client, "ann@example.com", "Ann")
    house = _create(client, ann, "Maple")
    reasons = {"bad@example.com": email.BAD_ADDRESS, "down@example.com": email.UNAVAILABLE}
    monkeypatch.setattr(email, "deliver", lambda to, subject, text: reasons.get(to))
    res = client.post(
        f"{API}/households/{house['id']}/email-invites",
        json={"emails": ["bad@example.com", "down@example.com", "ok@example.com"]},
        headers=ann,
    ).json()["results"]
    assert res == [
        {"email": "bad@example.com", "status": "failed", "reason": "bad_address"},
        {"email": "down@example.com", "status": "failed", "reason": "unavailable"},
        {"email": "ok@example.com", "status": "sent", "reason": None},
    ]


def test_email_failures_are_classified():
    assert email._reason(400, '{"code":"invalid_parameter","message":"email is not valid in to"}') == email.BAD_ADDRESS
    assert email._reason(422, '{"message":"Invalid `to` field. Please use our testing email address"}') == email.REFUSED
    assert email._reason(503, "") == email.UNAVAILABLE and email._reason(429, "") == email.UNAVAILABLE
    assert email._reason(401, '{"message":"Key not found"}') == email.REFUSED
