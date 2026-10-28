"""Trains the voice model: `python -m voice_training.train` (from backend/).

Fills the example phrases in, checks accuracy on a held-back fifth, then trains on all of them and
writes app/services/voice_model.json (a few tens of KB; it ships with the backend).
"""

import json
import random
import re

from app.services import voice_local
from voice_training.phrases import GROCERIES, INTENTS, MESSAGES, TASKS

FILLS = {"grocery": GROCERIES, "message": MESSAGES, "task": TASKS}


def expand(template: str, rng: random.Random, copies: int = 4) -> list[str]:
    if "{" not in template:
        return [template]
    return [
        re.sub(r"\{(\w+)\}", lambda m: rng.choice(FILLS[m.group(1)]), template)
        for _ in range(copies)
    ]


def examples(seed: int = 7) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    return [
        (text, intent)
        for intent, templates in INTENTS.items()
        for t in templates
        for text in expand(t, rng)
    ]


def main() -> None:
    data = examples()
    rng = random.Random(1)
    rng.shuffle(data)
    cut = len(data) // 5
    held, rest = data[:cut], data[cut:]
    model = voice_local.train(rest)
    voice_local.MODEL_PATH.write_text(json.dumps(model))
    voice_local._model.cache_clear()
    right = sum(voice_local.classify(voice_local.normalize(t))[0][0] == i for t, i in held)
    print(f"held-back accuracy: {right}/{len(held)} ({right / len(held):.0%})")

    model = voice_local.train(data)
    voice_local.MODEL_PATH.write_text(json.dumps(model, separators=(",", ":"), sort_keys=True))
    voice_local._model.cache_clear()
    size = voice_local.MODEL_PATH.stat().st_size
    print(
        f"trained on {len(data)} phrases, {len(INTENTS)} intents → {voice_local.MODEL_PATH.name} ({size // 1024} KB)"
    )


if __name__ == "__main__":
    main()
