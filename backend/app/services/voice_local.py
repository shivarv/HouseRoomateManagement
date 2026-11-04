"""Understanding a voice command on our own server: no outside service, no cost.

Two parts, each doing what it's good at:

1. **Matching** finds who and what against this house's own data: people (with nicknames and
   close spellings, "Rajj" → Rajesh), today's chores ("trash" → "Dispose garbage"), bills ("internet"
   → WiFi), the grocery list, open favours, and amounts. Each match is swapped for a placeholder
   ("raj took out the trash" → "<person> took out the <chore>"), so the model never needs to know
   anyone's names.
2. **A tiny trained model** (naive Bayes over words and word pairs, `voice_model.json`, trained by
   `voice_training/train.py` on example phrases) says what kind of action that is.

The result is the same tool calls Claude would make (see `voice.TOOLS`), so everything after this
(the checks, the cards, Confirm, Undo) is shared. When unsure it asks back instead of guessing.
"""

import json
import math
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path

MODEL_PATH = Path(__file__).with_name("voice_model.json")
CONFIDENT = 0.6  # below this the model's best guess isn't trusted
NOT_SURE = "Not sure what you meant. Try something like “I did the dishes” or “add milk”."

PLACEHOLDERS = ("<person>", "<chore>", "<bill>", "<item>", "<favour>", "<num>")


# --- Words ---------------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Lowercase, no apostrophes ("didn't" → "didnt"), amounts as "<num>", punctuation as spaces."""
    text = text.lower().replace("’", "'")
    text = re.sub(
        r"\$?\b\d+(?:[.,]\d{1,2})?\b(?:\s*(?:dollars|bucks|rupees|rs|euros|pounds))?",
        " <num> ",
        text,
    )
    text = text.replace("'", "")
    return " ".join(re.findall(r"<\w+>|[a-z0-9]+", text))


def tokens(text: str) -> list[str]:
    return re.findall(r"<\w+>|[a-z0-9]+", text)


def stem(word: str) -> str:
    """Rough English endings, enough to match "cooked", "cooking" and "cook"."""
    w = word.lower()
    for suffix, keep in (("ies", "y"), ("ied", "y")):
        if w.endswith(suffix) and len(w) > 4:
            return w[: -len(suffix)] + keep
    for suffix in ("ing", "ed"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            w = w[: -len(suffix)]
            if len(w) > 2 and w[-1] == w[-2] and w[-1] not in "ls":  # mopped → mop
                w = w[:-1]
            return w
    if re.search(r"(sh|ch|x|ss)es$", w):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def features(text: str) -> list[str]:
    """What the model looks at: each word and each pair of neighbouring words."""
    words = tokens(text)
    pairs = zip(["^", *words], [*words, "$"], strict=True)
    return [f"w:{w}" for w in words] + [f"p:{a}_{b}" for a, b in pairs]


# --- The model -----------------------------------------------------------------------------


@cache
def _model() -> dict:
    return json.loads(MODEL_PATH.read_text())


def classify(masked: str) -> list[tuple[str, float]]:
    """Intents, most likely first, with probabilities."""
    model = _model()
    vocab = model["vocab_size"]
    scores = {}
    feats = features(masked)
    for intent, counts in model["counts"].items():
        total = model["totals"][intent]
        score = math.log(model["docs"][intent] / model["n_docs"])
        for f in feats:
            score += math.log((counts.get(f, 0) + 1) / (total + vocab))
        scores[intent] = score
    top = max(scores.values())
    exp = {k: math.exp(v - top) for k, v in scores.items()}
    norm = sum(exp.values())
    return sorted(((k, v / norm) for k, v in exp.items()), key=lambda kv: -kv[1])


def train(examples: list[tuple[str, str]]) -> dict:
    """Word counts per intent, from (masked phrase, intent) pairs. Used by voice_training/train.py."""
    counts: dict[str, dict[str, int]] = {}
    docs: dict[str, int] = {}
    vocab: set[str] = set()
    for text, intent in examples:
        bucket = counts.setdefault(intent, {})
        docs[intent] = docs.get(intent, 0) + 1
        for f in features(normalize(text)):
            bucket[f] = bucket.get(f, 0) + 1
            vocab.add(f)
    return {
        "counts": counts,
        "totals": {k: sum(v.values()) for k, v in counts.items()},
        "docs": docs,
        "n_docs": sum(docs.values()),
        "vocab_size": len(vocab),
    }


# --- Matching against the house -----------------------------------------------------------

STOP = {
    "other",  # "Cleaning Hall and Other": filler in a chore's name, not a way to tell chores apart
    "others",
    "stuff",
    "things",
    "general",
    "the",
    "a",
    "an",
    "my",
    "our",
    "your",
    "his",
    "her",
    "their",
    "of",
    "to",
    "for",
    "on",
    "in",
    "at",
    "and",
    "or",
    "with",
    "it",
    "is",
    "was",
    "be",
    "this",
    "that",
    "some",
    "all",
    "up",
    "out",
    "off",
    "i",
    "me",
    "we",
    "you",
    "he",
    "she",
    "they",
    "did",
    "do",
    "done",
    "just",
    "please",
    "today",
}
# Verbs that say "a chore was done" without saying which one: only used if nothing better matches.
GENERIC = {"clean", "take", "took", "wash", "empty", "tidy", "make", "put", "help", "pick", "get"}
# Words that mean the same thing for matching chores and bills (all stemmed).
SYNONYMS = [
    {"trash", "garbage", "bin", "rubbish", "waste", "dispose"},
    {"dish", "washing", "plate", "utensil", "dishwasher"},
    {"cook", "dinner", "meal", "lunch", "breakfast", "food"},
    {"hall", "hallway", "corridor", "entrance", "lobby"},
    {"bathroom", "toilet", "washroom", "restroom", "loo", "shower"},
    {"vacuum", "hoover"},
    {"mop", "floor"},
    {"laundry", "cloth", "clothe"},
    {"plant", "garden"},
    {"recycl", "recycle", "recycling"},
    {"wifi", "internet", "broadband", "wi", "fi"},
    {"electricity", "electric", "power", "light", "current", "eb", "hydro"},
    {"rent", "lease"},
]


def _keywords(name: str) -> set[str]:
    words = {stem(w) for w in tokens(normalize(name))} - {stem(s) for s in STOP}
    for group in SYNONYMS:
        if words & group:
            words |= group
    return words


def _close(a: str, b: str) -> bool:
    return a == b or (len(a) >= 4 and len(b) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.84)


SOUNDS = [
    ("ph", "f"), ("ck", "k"), ("kh", "k"), ("q", "k"), ("sh", "s"), ("th", "t"), ("ee", "i"), ("ea", "i"),
    ("ie", "i"), ("ay", "ai"), ("ey", "ai"), ("ei", "ai"), ("oo", "u"), ("ou", "u"), ("y", "i"), ("z", "s"),
    ("w", "v"),
]


def _sound(word: str) -> str:
    """Roughly how a name sounds, so speech-to-text spellings match: Jay = Jai, Vicky = Vikki."""
    for a, b in SOUNDS:
        word = word.replace(a, b)
    word = re.sub(r"(.)\1+", r"\1", word)  # vikki → viki
    return word.rstrip("h") or word


def _name_fits(word: str, name: str) -> bool:
    """ "rajesh", "raj" (a short form), "rajj" (misheard) all fit Rajesh; "jay" fits Jai."""
    if _close(word, name) or (len(word) >= 3 and _sound(word) == _sound(name)):
        return True
    word, name = _sound(word), _sound(name)
    if (
        len(word) >= 3 and len(name) >= 3 and SequenceMatcher(None, word, name).ratio() >= 0.8
    ):  # rajj ~ raj
        return True
    if len(word) >= 3 and len(name) > len(word) and name[:2] == word[:2]:
        return SequenceMatcher(None, word, name[: len(word)]).ratio() >= 0.75
    return False


@dataclass
class Match:
    """What matched where: placeholder per token, and the candidates found."""

    words: list[str]
    masked: list[str]
    people: list[list[str]] = field(default_factory=list)  # per mention: member ids that fit
    chores: list[str] = field(default_factory=list)  # turn or open-chore ids, best first
    bills: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    favours: list[str] = field(default_factory=list)
    amounts: list[float] = field(default_factory=list)
    mentions_me: bool = False

    def text(self) -> str:
        out: list[str] = []
        for w in self.masked:  # "<item> <item>" (peanut butter) reads as one item
            if not (out and w in PLACEHOLDERS and out[-1] == w):
                out.append(w)
        return " ".join(out)


def _people(house: dict) -> list[tuple[str, set[str]]]:
    out = []
    for p in house["people"]:
        names = {w for n in (p["name"], p.get("also_called") or "") for w in tokens(normalize(n))}
        out.append((p["id"], {n for n in names if len(n) >= 2}))
    return out


def _things(house: dict) -> dict[str, list[tuple[str, set[str], set[str]]]]:
    """For each kind: (id, strong keywords, generic keywords)."""

    def entry(key, name):
        words = _keywords(name)
        return (key, words - GENERIC, words & GENERIC)

    turns = [entry(t["id"], t["chore"]) for t in house["todays_turns"]]
    open_chores = [entry(c["id"], c["chore"]) for c in house["chores_anyone_can_do"]]
    favour_words = {
        "pick",
        "up",
        "get",
        "grab",
        "help",
        "someone",
        "can",
        "need",
        "favour",
        "favor",
    }
    return {
        "chore": turns + open_chores,
        "bill": [entry(b["id"], b["name"]) for b in house["bills"]],
        "item": [entry(g["id"], g["name"]) for g in house["grocery_list"]],
        "favour": [
            (f["id"], _keywords(f["title"]) - favour_words - GENERIC, set())
            for f in house["open_favours"]
        ],
    }


def match(text: str, house: dict, amounts: list[float], chosen: str | None = None) -> Match:
    words = tokens(text)
    m = Match(words=words, masked=list(words), amounts=amounts)
    me = next(p["id"] for p in house["people"] if p.get("is_me"))
    people = _people(house)
    things = _things(house)
    scores: dict[str, dict[str, int]] = {k: {} for k in things}

    for i, word in enumerate(words):
        if word in ("i", "me", "myself", "im", "ive", "ill", "id"):
            m.mentions_me = True
            continue
        if word in PLACEHOLDERS or word in STOP or len(word) < 2:
            continue
        s = stem(word)
        exact = [pid for pid, names in people if word in names or word.rstrip("s") in names]
        # An exact chore, bill or item word ("hall") wins over a name it only looks like (Hal).
        is_thing = any(s in strong for entries in things.values() for _, strong, _ in entries)
        close = [
            pid
            for pid, names in people
            if any(_name_fits(word, n) or _name_fits(word.rstrip("s"), n) for n in names)
        ]
        # Raj and Rajesh both fit "raj", even though Raj is exact: that's asked, never guessed.
        found = list(dict.fromkeys(exact + ([] if is_thing and not exact else close)))
        if chosen in found:  # the name they tapped when asked "Did you mean …?"
            found = [chosen]
        if found:
            if found == [me]:
                m.mentions_me = True
            else:
                m.people.append(found)
                m.masked[i] = "<person>"
            continue
        for kind, entries in things.items():
            for key, strong, generic in entries:
                if any(_close(s, k) for k in strong):
                    scores[kind][key] = scores[kind].get(key, 0) + 2
                    if m.masked[i] == word:
                        m.masked[i] = f"<{kind}>"
                elif s in generic:
                    scores[kind][key] = scores[kind].get(key, 0) + 1

    def best(kind: str) -> list[str]:
        strong = {k: v for k, v in scores[kind].items() if v >= 2}
        if not strong:
            # Only a general word ("cleaning") matched: fine if it's in just one chore's name.
            weak = [k for k, v in scores[kind].items() if v >= 1]
            return weak if len(weak) == 1 else []
        top = max(strong.values())
        return [k for k, v in strong.items() if v == top]

    m.chores, m.bills, m.favours = best("chore"), best("bill"), best("favour")
    # Several items can be named at once ("eggs and peanut butter"): keep every one that matched.
    m.items = [k for k, v in scores["item"].items() if v >= 2]
    return m


# --- From words to tool calls -------------------------------------------------------------

CHAT_LEAD = re.compile(
    r"^(?:please\s+)?(?:tell|message|text|let|remind|announce|post|say|send|inform|notify)\b.*?"
    r"\b(?:everyone|everybody|house|group|chat|all|guys|roommates|housemates)\b"
    r"(?:\s+(?:know|in the chat|a message|saying|that))*[\s:,]*",
    re.IGNORECASE,
)
FAVOUR_LEAD = re.compile(
    r"^(?:hey\s+)?(?:can|could|would|will)\s+(?:someone|somebody|anyone|anybody|you guys|one of you)"
    r"(?:\s+please)?\s+|^(?:i need|need)\s+(?:someone|somebody|a hand|help)\s+(?:to\s+|with\s+)?"
    r"|^(?:someone|somebody|anyone)\s+(?:please\s+)?|^(?:ask|asking)\s+(?:the house|someone|everyone)\s+(?:to\s+)?",
    re.IGNORECASE,
)
GROCERY_LEAD = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?(?:add|put|we need|need|we(?:'| a)?re out of|out of|we ran out of|"
    r"ran out of|buy|get|running low on|low on|we don'?t have|no more|remember to buy|we should get|grocery|"
    r"shopping list)\s+",
    re.IGNORECASE,
)
GROCERY_TAIL = re.compile(
    r"\s+(?:to|on|onto)\s+(?:the\s+)?(?:grocery|shopping)?\s*(?:list|groceries)\s*$|\s+please$",
    re.IGNORECASE,
)
FILLER = re.compile(r"^(?:um+|uh+|hey|ok|okay|so|well|oh)[\s,]+", re.IGNORECASE)
# A part of a sentence with none of these can't stand alone ("eggs" in "add milk and eggs").
ACTION_WORDS = {
    "did",
    "done",
    "finished",
    "completed",
    "cleaned",
    "cooked",
    "took",
    "washed",
    "mopped",
    "vacuumed",
    "emptied",
    "handled",
    "bought",
    "got",
    "grabbed",
    "picked",
    "purchased",
    "paid",
    "settled",
    "covered",
    "add",
    "need",
    "remove",
    "delete",
    "tell",
    "message",
    "can",
    "could",
    "undo",
    "didnt",
    "isnt",
    "wasnt",
    "helped",
    "sorted",
    "ran",
    "out",
    "low",
    "mark",
    "pay",
    "buy",
}
EVERYTHING = {"everything", "all", "groceries", "shopping", "lot"}


def _clean(text: str) -> str:
    text = re.sub(r"\bi\b", "I", FILLER.sub("", text.strip()).rstrip(" .,"))
    return text[:1].upper() + text[1:] if text else text


def _split(raw: str, house: dict) -> list[str]:
    """Clauses: "I cooked and Raj did the trash" → two. A part that can't stand alone ("eggs")
    is joined back to the one before ("add milk and eggs")."""
    parts = re.split(
        r"\s*(?:,|;|\band then\b|\bthen\b|\band also\b|\balso\b|\band\b|\bplus\b)\s*",
        raw,
        flags=re.I,
    )
    clauses: list[str] = []
    for part in (p.strip() for p in parts):
        if not part:
            continue
        m = match(normalize(part), house, [])
        stands_alone = set(m.words) & ACTION_WORDS or {"<chore>", "<bill>"} & set(m.masked)
        # "...and I paid it": about the thing just named, not a new one.
        about_previous = set(m.words) & {"it", "that", "them", "this"} and not set(m.masked) & set(
            PLACEHOLDERS
        )
        if clauses and (not stands_alone or about_previous):
            clauses[-1] += f" and {part}"
        else:
            clauses.append(part)
    return clauses or [raw]


def _ask(question: str, options: list[str]) -> tuple[str, dict]:
    return ("ask_back", {"question": question, "options": options[:5]})


def _not(reason: str) -> tuple[str, dict]:
    return ("cannot_do", {"reason": reason})


def _names(house: dict, kind: str, ids: list[str]) -> list[str]:
    table = {
        "chore": [(t["id"], t["chore"]) for t in house["todays_turns"]]
        + [(c["id"], c["chore"]) for c in house["chores_anyone_can_do"]],
        "bill": [(b["id"], b["name"]) for b in house["bills"]],
        "favour": [(f["id"], f["title"]) for f in house["open_favours"]],
        "person": [(p["id"], p["name"]) for p in house["people"]],
    }[kind]
    return [name for key, name in table if key in ids]


def _who(m: Match, house: dict) -> tuple[str | None, tuple[str, dict] | None]:
    """Who did it: the person named, else me. Two people fit one name → ask which."""
    if not m.people:
        return None, None
    fits = m.people[0]
    # Tapping an answer adds the full name ("raj cooked Rajesh Kumar"): that settles it.
    settled = next(
        (later[0] for later in m.people[1:] if len(later) == 1 and later[0] in fits), None
    )
    if settled:
        return settled, None
    if len(fits) > 1:  # Raj and Rajesh both fit "raj": never guess who gets the credit
        names = _names(house, "person", fits)
        return None, _ask(f"Did you mean {', '.join(names[:-1])} or {names[-1]}?", names)
    return fits[0], None


def _grocery_names(raw: str) -> list[str]:
    raw = GROCERY_TAIL.sub("", GROCERY_LEAD.sub("", raw))
    names = []
    for part in re.split(r"\s*(?:,|\band\b|\bplus\b)\s*", raw):
        part = re.sub(r"^(?:some|more|a|an|the|few|couple of|bit of)\s+", "", part.strip())
        if part and part not in STOP:
            names.append(part)
    return names


def _clause(
    text: str,
    raw: str,
    house: dict,
    tab: str | None,
    amounts: list[float],
    chosen: str | None = None,
) -> list[tuple[str, dict]]:
    m = match(text, house, amounts, chosen)
    ranked = classify(m.text())
    intent, confidence = ranked[0]
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 0.15 and tab:  # a tie: the screen decides
        preferred = TAB_INTENTS.get(tab, set())
        intent = next((i for i, _ in ranked[:2] if i in preferred), intent)
    if confidence < CONFIDENT or intent == "other":
        return [_not(NOT_SURE)]

    if intent in ("complete_chore", "undo_chore"):
        doer, ask = _who(m, house)
        if ask:
            return [ask]
        turn_ids = {t["id"] for t in house["todays_turns"]}
        chores = m.chores if intent == "complete_chore" else [c for c in m.chores if c in turn_ids]
        if not chores:
            names = _names(
                house,
                "chore",
                [t["id"] for t in house["todays_turns"]]
                + [c["id"] for c in house["chores_anyone_can_do"]],
            )
            return [_ask("Which chore?", names)] if names else [_not("There are no chores today.")]
        if len(chores) > 1:
            return [_ask("Which one?", _names(house, "chore", chores))]
        chore = chores[0]
        if intent == "undo_chore":
            return [("reopen_task", {"task": chore})]
        if chore in turn_ids:
            return [("complete_task", {"task": chore, "done_by": doer})]
        return [("log_open_chore", {"chore": chore, "done_by": doer})]

    if intent == "pay_bill":
        payer, ask = _who(m, house)
        if ask:
            return [ask]
        if len(m.bills) != 1:
            ids = m.bills or [b["id"] for b in house["bills"] if b["status"] != "paid"]
            return (
                [_ask("Which bill?", _names(house, "bill", ids))]
                if ids
                else [_not("No bills are waiting to be paid.")]
            )
        return [
            (
                "pay_bill",
                {
                    "bill": m.bills[0],
                    "paid_by": payer,
                    "amount": m.amounts[0] if m.amounts else None,
                },
            )
        ]

    if intent == "add_groceries":
        names = _grocery_names(raw)
        return (
            [("add_groceries", {"names": names})]
            if names
            else [_not("Say what to add, e.g. “add milk and eggs”.")]
        )

    if intent in ("mark_bought", "favour_done") and not (
        m.items if intent == "mark_bought" else m.favours
    ):
        # "I picked up Ann's parcel" can be a favour; "got the eggs" a grocery: go by what matched.
        intent = "favour_done" if m.favours else "mark_bought" if m.items else intent

    if intent == "mark_bought":
        if m.items:
            return [("mark_bought", {"items": m.items})]
        if set(m.words) & EVERYTHING and house["grocery_list"]:
            return [("mark_bought", {"items": [g["id"] for g in house["grocery_list"]]})]
        return [_not("Couldn't find that on the grocery list.")]

    if intent == "remove_grocery":
        return (
            [("remove_grocery", {"items": m.items})]
            if m.items
            else [_not("Couldn't find that on the grocery list.")]
        )

    if intent == "favour_done":
        if len(m.favours) == 1:
            return [("favour_done", {"favour": m.favours[0]})]
        ids = m.favours or [f["id"] for f in house["open_favours"]]
        return (
            [_ask("Which favour?", _names(house, "favour", ids))]
            if ids
            else [_not("There are no open favours.")]
        )

    if intent == "send_chat":
        message = _clean(CHAT_LEAD.sub("", raw))
        return [("send_chat", {"text": message})] if message else [_not("Say what to send.")]

    if intent == "ask_favour":
        title = _clean(re.sub(r"\s+(?:please|for me please)$", "", FAVOUR_LEAD.sub("", raw)))
        return (
            [("ask_favour", {"title": title[:120], "details": None})] if title else [_not(NOT_SURE)]
        )

    return [_not(NOT_SURE)]


TAB_INTENTS = {
    "today": {"complete_chore", "undo_chore"},
    "groceries": {"add_groceries", "mark_bought", "remove_grocery"},
    "reminders": {"pay_bill"},
    "chat": {"send_chat"},
    "favours": {"ask_favour", "favour_done"},
}


def interpret(
    house: dict, said: str, tab: str | None = None, answer: str | None = None
) -> list[tuple[str, dict]]:
    """What was said → tool calls, the same ones Claude would make (short ids from `house`)."""
    def tidy(text: str) -> str:
        text = re.sub(r"\s+", " ", text.replace("\u2019", "'")).strip()
        return FILLER.sub("", re.sub(r"[^\w\s:,;'.$-]", "", text))

    raw = tidy(said)

    # A name tapped in answer to "Did you mean Raj or Rajesh?" is that person, exactly.
    chosen = None
    if answer:
        wanted = answer.strip().lower()
        chosen = next(
            (
                p["id"]
                for p in house["people"]
                if wanted in (p["name"].lower(), (p.get("also_called") or "").lower())
            ),
            None,
        )

    # A chat message or a favour keeps its own "and"s: don't split those.
    clauses = [raw] if CHAT_LEAD.match(raw) or FAVOUR_LEAD.match(raw) else _split(raw, house)
    calls: list[tuple[str, dict]] = []
    for clause in clauses:
        amounts = [
            float(a.replace(",", ".")) for a in re.findall(r"\b\d+(?:[.,]\d{1,2})?\b", clause)
        ]
        found = _clause(normalize(clause), clause, house, tab, amounts, chosen)
        if answer and any(name == "ask_back" for name, _ in found):
            # The answer finishes the part that asked, as one piece ("Cleaning Hall and Other").
            whole = f"{clause} {tidy(answer)}"
            found = _clause(normalize(whole), whole, house, tab, amounts, chosen)
        calls.extend(found)

    # The same action twice (said twice, or matched twice) is one card.
    unique = list({json.dumps(c, sort_keys=True): c for c in calls}.values())
    # Several clauses where one wasn't understood: keep the ones that were.
    good = [c for c in unique if c[0] != "cannot_do" or len(unique) == 1]
    return good or unique
