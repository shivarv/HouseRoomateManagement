from tests.conftest import register
from tests.test_chore_api import API
from tests.test_help import _house


def _send(client, house, headers, body):
    return client.post(f"{API}/households/{house['id']}/chat", json={"body": body}, headers=headers)


def _page(client, house, headers, **params):
    res = client.get(f"{API}/households/{house['id']}/chat", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _unread(client, house, headers):
    return client.get(f"{API}/households/{house['id']}/chat/unread", headers=headers).json()["count"]


def test_send_read_and_unread(client):
    house, ann, bea, cy = _house(client)
    res = _send(client, house, ann, "  Who's cooking tonight?\nI can do it  ")
    assert res.status_code == 201
    msg = res.json()
    assert msg["body"] == "Who's cooking tonight?\nI can do it" and msg["is_mine"] and msg["author"]["display_name"] == "Ann"
    assert _send(client, house, ann, "   ").status_code == 422

    assert _unread(client, house, ann) == 0  # my own message
    assert _unread(client, house, bea) == 1
    _send(client, house, cy, "I'll buy rice")
    assert _unread(client, house, bea) == 2

    page = _page(client, house, bea)
    assert [m["body"] for m in page["messages"]] == ["Who's cooking tonight?\nI can do it", "I'll buy rice"]
    assert page["has_more"] is False
    client.post(f"{API}/households/{house['id']}/chat/read", headers=bea)
    assert _unread(client, house, bea) == 0


def test_paging_and_polling(client):
    house, ann, bea, _ = _house(client)
    for i in range(5):
        _send(client, house, ann, f"m{i}")
    first = _page(client, house, bea, limit=2)
    assert [m["body"] for m in first["messages"]] == ["m3", "m4"] and first["has_more"]
    older = _page(client, house, bea, limit=2, before=first["messages"][0]["created_at"])
    assert [m["body"] for m in older["messages"]] == ["m1", "m2"]

    since = first["messages"][-1]["created_at"]
    assert _page(client, house, bea, after=since)["messages"] == []
    _send(client, house, ann, "new one")
    assert [m["body"] for m in _page(client, house, bea, after=since)["messages"]] == ["new one"]


def test_edit_and_delete(client):
    house, ann, bea, cy = _house(client)  # Ann is the admin
    msg = _send(client, house, bea, "Rent is due").json()
    assert client.patch(f"{API}/chat-messages/{msg['id']}", json={"body": "x"}, headers=cy).status_code == 403
    res = client.patch(f"{API}/chat-messages/{msg['id']}", json={"body": "Rent is due Friday"}, headers=bea)
    assert res.status_code == 200 and res.json()["edited_at"] and res.json()["body"] == "Rent is due Friday"

    # An edit shows up when polling since before it.
    changed = _page(client, house, cy, after=msg["created_at"])["messages"]
    assert [m["body"] for m in changed] == ["Rent is due Friday"]

    assert client.delete(f"{API}/chat-messages/{msg['id']}", headers=cy).status_code == 403
    res = client.delete(f"{API}/chat-messages/{msg['id']}", headers=ann)  # admins can
    assert res.status_code == 200 and res.json()["deleted"] and res.json()["body"] == ""
    shown = _page(client, house, cy)["messages"][0]
    assert shown["deleted"] and shown["body"] == "" and not shown["can_delete"]
    assert client.patch(f"{API}/chat-messages/{msg['id']}", json={"body": "y"}, headers=bea).status_code == 400
    assert _unread(client, house, cy) == 0  # deleted messages don't count


def test_other_houses_cant_read_or_post(client):
    house, ann, _, _ = _house(client)
    _send(client, house, ann, "private")
    zed = register(client, "zed@example.com", "Zed")
    assert client.get(f"{API}/households/{house['id']}/chat", headers=zed).status_code == 404
    assert _send(client, house, zed, "hi").status_code == 404
