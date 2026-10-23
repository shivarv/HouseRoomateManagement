from app.services import email
from tests.conftest import register
from tests.test_chore_api import API
from tests.test_last_household import _create


def test_email_invites_are_saved_shown_to_the_invited_person_and_settled_on_join(client, monkeypatch):
    sent = []
    monkeypatch.setattr(email, "deliver", lambda to, subject, text, html=None: sent.append((to, subject, text)) or email.NOT_SET_UP)
    ann = register(client, "ann@example.com", "Ann")
    maple = _create(client, ann, "Maple")

    res = client.post(
        f"{API}/households/{maple['id']}/email-invites",
        json={"emails": ["Bea@Example.com", "bea@example.com", "ann@example.com"]},
        headers=ann,
    )
    assert res.status_code == 200
    body = res.json()
    # No email service: saved, not sent. Duplicates collapse; members are skipped.
    assert body["results"] == [
        {"email": "bea@example.com", "status": "saved", "reason": None},
        {"email": "ann@example.com", "status": "member", "reason": None},
    ]
    assert body["link"].endswith(f"/join/{maple['invite_code']}") and body["email_enabled"] is False
    invite_mails = [m for m in sent if "Confirm your email" not in m[1]]  # sign-up sends a verification email too
    assert invite_mails and invite_mails[0][0] == "bea@example.com" and "/invite/" in invite_mails[0][2]

    pending = client.get(f"{API}/households/{maple['id']}/email-invites", headers=ann).json()
    assert [p["email"] for p in pending] == ["bea@example.com"] and pending[0]["last_sent_at"] is None

    # Bea signs up with that email: her welcome screen shows the invite.
    bea = register(client, "bea@example.com", "Bea")
    mine = client.get(f"{API}/me/invites", headers=bea).json()
    assert [(m["household_name"], m["invited_by"]) for m in mine] == [("Maple", "Ann")]

    client.post(f"{API}/invites/{mine[0]['invite_code']}/accept", json={}, headers=bea)
    assert client.get(f"{API}/me/invites", headers=bea).json() == []
    assert client.get(f"{API}/households/{maple['id']}/email-invites", headers=ann).json() == []


def test_sent_invites_are_marked_and_only_admins_or_the_sender_cancel(client, monkeypatch):
    monkeypatch.setattr(email, "deliver", lambda to, subject, text, html=None: None)
    ann = register(client, "ann@example.com", "Ann")
    maple = _create(client, ann, "Maple")
    cy = register(client, "cy@example.com", "Cy")
    client.post(f"{API}/invites/{maple['invite_code']}/accept", json={}, headers=cy)

    res = client.post(f"{API}/households/{maple['id']}/email-invites", json={"emails": ["dev@example.com"]}, headers=ann)
    assert res.json()["results"][0]["status"] == "sent"
    pending = client.get(f"{API}/households/{maple['id']}/email-invites", headers=cy).json()
    assert pending[0]["last_sent_at"] is not None and pending[0]["can_cancel"] is False

    assert client.delete(f"{API}/email-invites/{pending[0]['id']}", headers=cy).status_code == 403
    assert client.delete(f"{API}/email-invites/{pending[0]['id']}", headers=ann).status_code == 204

    outsider = register(client, "zed@example.com", "Zed")
    bad = client.post(f"{API}/households/{maple['id']}/email-invites", json={"emails": ["a@b.co"]}, headers=outsider)
    assert bad.status_code == 404
    assert client.post(f"{API}/households/{maple['id']}/email-invites", json={"emails": ["nope"]}, headers=ann).status_code == 422
