import json
import random
from typing import List

POSITIVE_WORDS = ["good", "great", "excellent", "amazing", "wonderful", "love", "like", "happy", "enjoy", "fantastic", "superb", "pleasant", "positive", "recommend"]
NEGATIVE_WORDS = ["bad", "terrible", "awful", "poor", "hate", "dislike", "sad", "angry", "boring", "horrible", "negative", "worse", "worst", "complain"]
NEUTRAL_WORDS = ["movie", "film", "story", "character", "plot", "music", "today", "yesterday", "people", "time", "place", "experience", "product", "service", "item", "food", "app", "game"]


def generate_example(pos_ratio: float = 0.5, min_len: int = 6, max_len: int = 20) -> dict:
    is_pos = 1 if random.random() < pos_ratio else 0
    length = random.randint(min_len, max_len)
    words: List[str] = []
    for _ in range(length):
        r = random.random()
        if r < 0.15:
            words.append(random.choice(POSITIVE_WORDS if is_pos else NEGATIVE_WORDS))
        elif r < 0.30:
            words.append(random.choice(NEGATIVE_WORDS if is_pos == 0 else POSITIVE_WORDS))
        else:
            words.append(random.choice(NEUTRAL_WORDS))
    # Add stronger signal
    for _ in range(2):
        words.append(random.choice(POSITIVE_WORDS if is_pos else NEGATIVE_WORDS))
    random.shuffle(words)
    return {"text": " ".join(words), "label": is_pos}


def generate_synthetic_jsonl(path: str, n: int, seed: int = 42):
    random.seed(seed)
    with open(path, "w", encoding="utf-8") as f:
        for _ in range(n):
            ex = generate_example(pos_ratio=0.5)
            f.write(json.dumps(ex) + "\n")

