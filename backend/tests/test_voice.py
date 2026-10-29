import json
import re

import pytest

from app.core.config import settings
from app.services import voice
from tests.test_chore_api import API
from tests.test_help import _house

# fake_today: Monday, Oct 19 2026. Ann (admin), Bea and Cy have accounts; Dev…Hal are names only.
# Today Ann cooks and Bea cleans the hall; garbage is open to anyone.


@pytest.fixture
def claude(monkeypatch):
    """Stands in for Claude: `claude.reply = lambda house: [(tool, args), ...]`, where `house` is
    the snapshot it was sent, so a test picks ids by name like Claude would."""

    class Fake:
        reply = staticmethod(lambda house: [])
        seen: list[str] = []

    fake = Fake()

    def ask(content):
        fake.seen.append(content)
        house = json.loads(re.search(r"<house>(.*)</house>", content).group(1))
        return voice.Answer(fake.reply(house), input_tokens=1200, output_tokens=80)

    monkeypatch.setattr(settings, "voice_engine", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(voice, "ask_claude", ask)
    return fake


def person(house, name):
    return next(p["id"] for p in house["people"] if p["name"] == name)


def turn(house, chore):
    return next(t["id"] for t in house["todays_turns"] if t["chore"] == chore)


def bill(house, name):
    return next(b["id"] for b in house["bills"] if b["name"] == name)


def grocery(house, name):
    return next(g["id"] for g in house["grocery_list"] if g["name"] == name)


def _say(client, house, headers, text, **body):
    res = client.post(
        f"{API}/households/{house['id']}/voice/interpret", json={"text": text, **body}, headers=headers
    )
    assert res.status_code == 200, res.text
    return res.json()


def _run(client, house, headers, actions, out, undo=False, status=200):
    """Confirm (or Undo) actions from `out`, what interpret returned."""
    res = client.post(
        f"{API}/households/{house['id']}/voice/execute",
        json={"actions": actions, "command_id": out["command_id"], "undo": undo},
        headers=headers,
    )
    assert res.status_code == status, res.text
    return res.json()["results"] if status == 200 else res.json()


def _today(client, house, headers):
    tasks = client.get(f"{API}/households/{house['id']}/tasks/today", headers=headers).json()["tasks"]
    return {t["chore"]["name"]: t for t in tasks}


def test_claude_is_off_without_a_key_and_voice_is_only_for_members(client, fake_today, monkeypatch):
    house, ann, bea, _ = _house(client)
    monkeypatch.setattr(settings, "voice_engine", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    assert client.get(f"{API}/voice/config", headers=ann).json() == {"enabled": False}
    res = client.post(f"{API}/households/{house['id']}/voice/interpret", json={"text": "hi"}, headers=ann)
    assert res.status_code == 503

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    assert client.get(f"{API}/voice/config", headers=ann).json() == {"enabled": True}
    from tests.conftest import register

    stranger = register(client, "zed@example.com", "Zed")
    res = client.post(f"{API}/households/{house['id']}/voice/interpret", json={"text": "hi"}, headers=stranger)
    assert res.status_code == 404


def test_someone_else_did_a_chore_confirm_then_undo(client, fake_today, claude):
    house, ann, bea, _ = _house(client)
    claude.reply = lambda h: [("complete_task", {"task": turn(h, "Clean hall"), "done_by": person(h, "Bea")})]

    out = _say(client, house, ann, "bea cleaned the hall", tab="today")
    [card] = out["proposals"]
    assert card["summary"] == "Clean hall · done by Bea" and card["area"] == "chores"
    assert "<tab>today</tab>" in claude.seen[-1] and "<said>bea cleaned the hall</said>" in claude.seen[-1]
    assert _today(client, house, ann)["Clean hall"]["status"] == "pending"  # nothing changed yet

    [result] = _run(client, house, ann, [card["action"]], out)
    assert result["ok"] and result["undo"][0]["type"] == "reopen_task"
    hall = _today(client, house, ann)["Clean hall"]
    assert hall["status"] == "done" and hall["completed_by"]["display_name"] == "Bea"

    [undone] = _run(client, house, ann, result["undo"], out, undo=True)
    assert undone["ok"] and _today(client, house, ann)["Clean hall"]["status"] == "pending"


def test_two_things_in_one_sentence(client, fake_today, claude):
    house, ann, bea, _ = _house(client)
    client.post(f"{API}/households/{house['id']}/shopping", json={"name": "Milk"}, headers=bea)
    claude.reply = lambda h: [
        ("complete_task", {"task": turn(h, "Cooking"), "done_by": None}),
        ("mark_bought", {"items": [grocery(h, "Milk")]}),
    ]
    out = _say(client, house, ann, "I cooked and bought the milk")
    assert [p["summary"] for p in out["proposals"]] == ["Cooking · done by you", "Bought: Milk"]
    results = _run(client, house, ann, [p["action"] for p in out["proposals"]], out)
    assert all(r["ok"] for r in results)
    shopping = client.get(f"{API}/households/{house['id']}/shopping", headers=ann).json()
    assert shopping["needed"] == [] and shopping["recently_bought"][0]["name"] == "Milk"


def test_made_up_ids_unknown_people_and_already_done_never_become_cards(client, fake_today, claude):
    house, ann, bea, _ = _house(client)
    claude.reply = lambda h: [("complete_task", {"task": "t99", "done_by": None})]
    out = _say(client, house, ann, "did the laundry")
    assert out["command_id"] and {k: v for k, v in out.items() if k != "command_id"} == {
        "proposals": [], "question": None, "options": [], "notes": ["Couldn't find that task."]
    }

    claude.reply = lambda h: [("complete_task", {"task": turn(h, "Cooking"), "done_by": "m42"})]
    assert _say(client, house, ann, "raj cooked")["notes"] == ["Couldn't find that person."]

    # Claude asks back instead of guessing, or says why not.
    claude.reply = lambda h: [("ask_back", {"question": "Who cooked?", "options": ["Bea", "Cy"]})]
    out = _say(client, house, ann, "raj cooked")
    assert out["question"] == "Who cooked?" and out["options"] == ["Bea", "Cy"]
    claude.reply = lambda h: [("complete_task", {"task": turn(h, "Cooking"), "done_by": person(h, "Bea")})]
    follow = _say(client, house, ann, "raj cooked", follow_up={"question": "Who cooked?", "answer": "Bea"})
    assert [p["summary"] for p in follow["proposals"]] == ["Cooking · done by Bea"]
    assert "They answered: Bea" in claude.seen[-1]

    claude.reply = lambda h: [("cannot_do", {"reason": "Settings aren't available by voice."})]
    assert _say(client, house, ann, "make me admin")["notes"] == ["Settings aren't available by voice."]

    # Done already: our own check says so even if Claude proposes it.
    cooking = _today(client, house, ann)["Cooking"]
    client.post(f"{API}/tasks/{cooking['id']}/complete", headers=bea)
    claude.reply = lambda h: [("complete_task", {"task": turn(h, "Cooking"), "done_by": None})]
    assert _say(client, house, ann, "I cooked")["notes"] == ["Cooking is already done, by Bea."]


def test_bills_with_an_amount_and_paid_twice(client, fake_today, claude):
    house, ann, bea, _ = _house(client)
    claude.reply = lambda h: [("pay_bill", {"bill": bill(h, "Gas"), "paid_by": None, "amount": 42.5})]
    out = _say(client, house, ann, "gas was 42.50 and I paid it")
    [card] = out["proposals"]
    assert card["summary"] == "Gas · Oct 2026 · $42.50 · paid by you"
    [result] = _run(client, house, ann, [card["action"]], out)
    assert result["ok"] and result["undo"][0]["type"] == "undo_payment"

    bills = {b["name"]: b for b in client.get(f"{API}/households/{house['id']}/bills", headers=ann).json()["bills"]}
    assert bills["Gas"]["current"]["status"] == "paid" and bills["Gas"]["current"]["amount_cents"] == 4250

    claude.reply = lambda h: [("pay_bill", {"bill": bill(h, "Gas"), "paid_by": person(h, "Bea"), "amount": None})]
    assert _say(client, house, bea, "I paid gas")["notes"] == ["Gas is already paid for Oct 2026, by Ann."]


def test_everything_is_checked_before_anything_runs(client, fake_today, claude):
    house, ann, bea, _ = _house(client)
    client.post(f"{API}/households/{house['id']}/shopping", json={"name": "Eggs"}, headers=bea)
    claude.reply = lambda h: [
        ("complete_task", {"task": turn(h, "Cooking"), "done_by": None}),
        ("mark_bought", {"items": [grocery(h, "Eggs")]}),
    ]
    out = _say(client, house, ann, "cooked and got eggs")
    cards = out["proposals"]
    # Bea buys the eggs before Ann taps Confirm.
    eggs = client.get(f"{API}/households/{house['id']}/shopping", headers=bea).json()["needed"][0]
    client.post(f"{API}/shopping/{eggs['id']}/bought", headers=bea)

    results = _run(client, house, ann, [c["action"] for c in cards], out)
    assert [r["ok"] for r in results] == [False, False]
    assert results[0]["error"] is None and results[1]["error"] == "Eggs was already bought, by Bea."
    assert _today(client, house, ann)["Cooking"]["status"] == "pending"  # nothing ran


def test_groceries_chat_favours_and_open_chores(client, fake_today, claude):
    house, ann, bea, _ = _house(client)
    hid = house["id"]
    claude.reply = lambda h: [("add_groceries", {"names": ["milk", "eggs", "Milk"]})]
    out = _say(client, house, ann, "add milk and eggs")
    [card] = out["proposals"]
    assert card["summary"] == "Add to groceries: Milk, Eggs"
    [added] = _run(client, house, ann, [card["action"]], out)
    assert [i["name"] for i in client.get(f"{API}/households/{hid}/shopping", headers=ann).json()["needed"]] == [
        "Milk", "Eggs"
    ]
    _run(client, house, ann, added["undo"], out, undo=True)  # Undo: both off the list again
    assert client.get(f"{API}/households/{hid}/shopping", headers=ann).json()["needed"] == []

    claude.reply = lambda h: [("send_chat", {"text": "I'll be late tonight"})]
    out = _say(client, house, ann, "tell everyone I'll be late")
    [card] = out["proposals"]
    assert card["summary"] == "Send to the house chat: “I'll be late tonight”"
    _run(client, house, ann, [card["action"]], out)
    chat = client.get(f"{API}/households/{hid}/chat", headers=bea).json()["messages"]
    assert chat[-1]["body"] == "I'll be late tonight"

    claude.reply = lambda h: [("ask_favour", {"title": "Pick up my parcel", "details": None})]
    out = _say(client, house, ann, "can someone pick up my parcel")
    _run(client, house, ann, [out["proposals"][0]["action"]], out)
    claude.reply = lambda h: [("favour_done", {"favour": h["open_favours"][0]["id"]})]
    out = _say(client, house, bea, "I picked up Ann's parcel")
    [card] = out["proposals"]
    assert card["summary"] == "Done: Pick up my parcel (asked by Ann)"
    [done] = _run(client, house, bea, [card["action"]], out)
    assert done["ok"] and done["undo"][0]["type"] == "reopen_favour"

    claude.reply = lambda h: [("log_open_chore", {"chore": h["chores_anyone_can_do"][0]["id"], "done_by": None})]
    out = _say(client, house, bea, "took out the trash")
    [card] = out["proposals"]
    assert card["summary"] == "Dispose garbage · done by you"
    [logged] = _run(client, house, bea, [card["action"]], out)
    assert logged["ok"] and logged["undo"][0]["type"] == "remove_log"


def test_someone_who_left_and_the_daily_limit(client, fake_today, claude, monkeypatch):
    house, ann, bea, _ = _house(client)
    claude.reply = lambda h: [("complete_task", {"task": turn(h, "Cooking"), "done_by": person(h, "Dev")})]
    out = _say(client, house, ann, "dev cooked")
    [card] = out["proposals"]
    dev = card["action"]["member_id"]
    assert client.delete(f"{API}/members/{dev}", headers=ann).status_code == 204
    [result] = _run(client, house, ann, [card["action"]], out)
    assert result["error"] == "Dev isn't in this house any more"

    claude.reply = lambda h: []
    monkeypatch.setattr(settings, "voice_daily_limit", 3)  # "dev cooked" was the first
    for _ in range(2):
        res = client.post(f"{API}/households/{house['id']}/voice/interpret", json={"text": "hi"}, headers=ann)
        assert res.status_code == 200
    res = client.post(f"{API}/households/{house['id']}/voice/interpret", json={"text": "hi"}, headers=ann)
    assert res.status_code == 409 and "3 times today" in res.text


def test_confirm_and_undo_each_run_once_and_activity_says_how(client, fake_today, claude):
    house, ann, bea, _ = _house(client)
    claude.reply = lambda h: [("log_open_chore", {"chore": h["chores_anyone_can_do"][0]["id"], "done_by": None})]
    out = _say(client, house, ann, "took out the trash")
    [card] = out["proposals"]

    # Tapping Confirm three times: open chores can be logged again and again, so only the
    # command being claimed stops the extra taps.
    [logged] = _run(client, house, ann, [card["action"]], out)
    for _ in range(2):
        assert _run(client, house, ann, [card["action"]], out, status=409)["detail"] == "Already done."
    feed = client.get(f"{API}/households/{house['id']}/activity", headers=ann).json()
    assert [(e["action"], e["via"]) for e in feed if e["chore_name"] == "Dispose garbage"] == [
        ("logged", "voice")
    ]

    # Undo can't run before Confirm, nor twice, nor for someone else's command.
    assert _run(client, house, bea, logged["undo"], out, undo=True, status=409)
    _run(client, house, ann, logged["undo"], out, undo=True)
    [again] = _run(client, house, ann, logged["undo"], out, undo=True)  # gone: the check says so
    assert not again["ok"] and again["error"] == "Log entry not found"
    feed = client.get(f"{API}/households/{house['id']}/activity", headers=ann).json()
    assert feed[0]["action"] == "log_removed" and feed[0]["via"] == "voice"

    # Typed to the assistant: says so. The buttons: nothing.
    claude.reply = lambda h: [("complete_task", {"task": turn(h, "Cooking"), "done_by": None})]
    out = _say(client, house, ann, "I cooked", input="typed")
    _run(client, house, ann, [out["proposals"][0]["action"]], out)
    hall = _today(client, house, bea)["Clean hall"]
    client.post(f"{API}/tasks/{hall['id']}/complete", headers=bea)
    feed = client.get(f"{API}/households/{house['id']}/activity", headers=ann).json()
    assert [(e["chore_name"], e["via"]) for e in feed[:2]] == [("Clean hall", None), ("Cooking", "typed")]


def test_a_confirm_that_couldnt_run_can_be_sent_again(client, fake_today, claude):
    house, ann, bea, _ = _house(client)
    client.post(f"{API}/households/{house['id']}/shopping", json={"name": "Eggs"}, headers=bea)
    claude.reply = lambda h: [
        ("complete_task", {"task": turn(h, "Cooking"), "done_by": None}),
        ("mark_bought", {"items": [grocery(h, "Eggs")]}),
    ]
    out = _say(client, house, ann, "cooked and got eggs")
    cards = out["proposals"]
    eggs = client.get(f"{API}/households/{house['id']}/shopping", headers=bea).json()["needed"][0]
    client.post(f"{API}/shopping/{eggs['id']}/bought", headers=bea)
    assert _run(client, house, ann, [c["action"] for c in cards], out)[1]["error"]
    # "Do the other 1": nothing ran, so the command isn't used up.
    [cooked] = _run(client, house, ann, [cards[0]["action"]], out)
    assert cooked["ok"] and _today(client, house, ann)["Cooking"]["status"] == "done"
