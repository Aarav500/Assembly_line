import random
import uuid
from datetime import datetime


def make_rng(seed=None):
    return random.Random(seed)


def uid(prefix=None):
    u = str(uuid.uuid4())
    return f"{prefix}_{u}" if prefix else u


def pick(rng, seq):
    return rng.choice(seq)


def pick_n(rng, seq, n):
    n = min(n, len(seq))
    return rng.sample(seq, n)


def pick_weighted(rng, choices):
    # choices: list of (item, weight)
    total = sum(w for _, w in choices)
    r = rng.uniform(0, total)
    upto = 0
    for item, weight in choices:
        if upto + weight >= r:
            return item
        upto += weight
    return choices[-1][0]


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def slugify(text):
    return ''.join(c.lower() if c.isalnum() else '-' for c in text).strip('-').replace('--', '-')

