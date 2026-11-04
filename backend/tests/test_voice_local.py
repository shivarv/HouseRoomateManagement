"""The free, on-server voice interpreter (app/services/voice_local.py)."""

import pytest

from app.services import voice_local
from tests.test_chore_api import API
from tests.test_help import _house

HOUSE = {
    "people": [
        {"id": "m1", "name": "Shiva", "is_me": True},
        {"id": "m2", "name": "Rajesh", "also_called": "Rajesh Kumar"},
        {"id": "m3", "name": "Priya"},
        {"id": "m4", "name": "Sam"},
    ],
    "todays_turns": [
        {"id": "t1", "chore": "Cooking", "done": False},
        {"id": "t2", "chore": "Clean hall", "done": False},
        {"id": "t3", "chore": "Wash dishes", "done": False},
    ],
    "chores_anyone_can_do": [{"id": "c1", "chore": "Dispose garbage"}],
    "bills": [
        {"id": "b1", "name": "Rent", "status": "overdue"},
        {"id": "b2", "name": "Electricity", "status": "due"},
        {"id": "b3", "name": "WiFi", "status": "due"},
        {"id": "b4", "name": "Gas", "status": "due"},
    ],
    "grocery_list": [
        {"id": "g1", "name": "Milk"},
        {"id": "g2", "name": "Eggs"},
        {"id": "g3", "name": "Peanut butter"},
    ],
    "open_favours": [{"id": "f1", "title": "Pick up my parcel", "asked_by": "m3"}],
}


def said(text, house=HOUSE, **kw):
    return voice_local.interpret(house, text, **kw)


@pytest.mark.parametrize(
    "text, calls",
    [
        ("I did the dishes", [("complete_task", {"task": "t3", "done_by": None})]),
        ("raj took out the trash", [("log_open_chore", {"chore": "c1", "done_by": "m2"})]),
        ("Rajj cleaned the hall", [("complete_task", {"task": "t2", "done_by": "m2"})]),
        ("rajesh did the cooking", [("complete_task", {"task": "t1", "done_by": "m2"})]),
        (
            "priya did the cooking and I did the dishes",
            [
                ("complete_task", {"task": "t1", "done_by": "m3"}),
                ("complete_task", {"task": "t3", "done_by": None}),
            ],
        ),
        (
            "I cooked and bought milk",
            [
                ("complete_task", {"task": "t1", "done_by": None}),
                ("mark_bought", {"items": ["g1"]}),
            ],
        ),
        ("I didn't do the dishes", [("reopen_task", {"task": "t3"})]),
        ("add bread and butter", [("add_groceries", {"names": ["bread", "butter"]})]),
        ("we're out of toilet paper", [("add_groceries", {"names": ["toilet paper"]})]),
        ("bought eggs and peanut butter", [("mark_bought", {"items": ["g2", "g3"]})]),
        ("I got everything", [("mark_bought", {"items": ["g1", "g2", "g3"]})]),
        ("remove milk", [("remove_grocery", {"items": ["g1"]})]),
        (
            "gas was 42.50 and I paid it",
            [("pay_bill", {"bill": "b4", "paid_by": None, "amount": 42.5})],
        ),
        (
            "Priya paid the internet",
            [("pay_bill", {"bill": "b3", "paid_by": "m3", "amount": None})],
        ),
        ("um so I paid rent", [("pay_bill", {"bill": "b1", "paid_by": None, "amount": None})]),
        (
            "tell everyone I'll be late tonight and dinner is in the fridge",
            [("send_chat", {"text": "I'll be late tonight and dinner is in the fridge"})],
        ),
        (
            "can someone water my plants please",
            [("ask_favour", {"title": "Water my plants", "details": None})],
        ),
        ("I picked up Priya's parcel", [("favour_done", {"favour": "f1"})]),
    ],
)
def test_everyday_phrases(text, calls):
    assert said(text) == calls


def test_similar_names_are_asked_never_guessed():
    house = {**HOUSE, "people": [*HOUSE["people"], {"id": "m5", "name": "Raj"}]}
    for text in ("raj cooked", "rajj cooked", "raju cooked"):
        [(tool, args)] = said(text, house)
        assert tool == "ask_back", text
        assert args == {"question": "Did you mean Rajesh or Raj?", "options": ["Rajesh", "Raj"]}
    # The full name fits only Rajesh: no need to ask (the card still says who).
    assert said("rajesh cooked", house) == [("complete_task", {"task": "t1", "done_by": "m2"})]
    # Tapping a name settles it.
    assert said("raj cooked", house, answer="Raj") == [
        ("complete_task", {"task": "t1", "done_by": "m5"})
    ]
    assert said("raj cooked", house, answer="Rajesh") == [
        ("complete_task", {"task": "t1", "done_by": "m2"})
    ]


def test_unclear_or_unknown_asks_back_or_says_why():
    assert said("I paid the bill")[0] == (
        "ask_back",
        {"question": "Which bill?", "options": ["Rent", "Electricity", "WiFi", "Gas"]},
    )
    assert said("I paid the bill", answer="Gas") == [
        ("pay_bill", {"bill": "b4", "paid_by": None, "amount": None})
    ]
    # "cleaned" is only in Clean hall's name, so that's the one; "did it" could be any chore.
    assert said("I cleaned") == [("complete_task", {"task": "t2", "done_by": None})]
    assert said("I did it")[0][0] == "ask_back"
    assert said("bought bananas") == [
        ("cannot_do", {"reason": "Couldn't find that on the grocery list."})
    ]
    for text in ("make me admin", "what's the weather", "hello"):
        assert said(text) == [("cannot_do", {"reason": voice_local.NOT_SURE})], text


def test_works_through_the_api_with_no_key(client, fake_today):
    """The default engine: no Anthropic key, nothing leaves the server."""
    house, ann, bea, _ = _house(client)
    assert client.get(f"{API}/voice/config", headers=ann).json() == {"enabled": True}
    res = client.post(
        f"{API}/households/{house['id']}/voice/interpret",
        json={"text": "bea cleaned the hall"},
        headers=ann,
    )
    assert res.status_code == 200, res.text
    [card] = res.json()["proposals"]
    assert card["summary"] == "Clean hall · done by Bea"
    run = client.post(
        f"{API}/households/{house['id']}/voice/execute",
        json={"actions": [card["action"]], "command_id": res.json()["command_id"]},
        headers=ann,
    )
    assert run.json()["results"][0]["ok"]


def test_names_that_sound_alike_and_chores_named_with_and():
    """What happened in a real house: "cleaning is done by Jay" for Jai and "Cleaning Hall and Other"."""
    house = {
        **HOUSE,
        "people": [*HOUSE["people"], {"id": "m5", "name": "Jai Vicky"}],
        "todays_turns": [
            {"id": "t1", "chore": "Cooking", "done": True},
            {"id": "t2", "chore": "Cleaning Hall and Other", "done": False},
        ],
    }
    expected = [("complete_task", {"task": "t2", "done_by": "m5"})]
    assert said("cleaning is done by Jay", house) == expected
    assert said("vicky did the cleaning", house) == expected
    # Tapping a chore whose name has "and" in it is one answer, and one card.
    assert said("Jay did it", house, answer="Cleaning Hall and Other") == expected
