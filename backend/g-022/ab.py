import hashlib
import random
from typing import Dict, Optional


def is_valid_variant(variant: str, weights: Dict[str, float]) -> bool:
    return variant in weights and weights[variant] > 0


def _hash_to_unit_interval(key: str) -> float:
    # Deterministic hash in [0,1)
    h = hashlib.sha256(key.encode("utf-8")).digest()
    # Take first 8 bytes as integer for performance
    val = int.from_bytes(h[:8], byteorder="big", signed=False)
    return (val % (10 ** 12)) / float(10 ** 12)


def _choose_by_weight(weights: Dict[str, float], hval: Optional[float] = None) -> str:
    # weights is a dict of variant -> probability (sum ~= 1)
    items = sorted(weights.items())  # stable order
    r = hval if hval is not None else random.random()
    c = 0.0
    for variant, w in items:
        c += w
        if r < c:
            return variant
    # In case of rounding errors, fallback to last
    return items[-1][0]


def assign_variant(user_id: Optional[str], weights: Dict[str, float], experiment_id: str) -> str:
    if user_id:
        hkey = f"{experiment_id}:{user_id}"
        hval = _hash_to_unit_interval(hkey)
        return _choose_by_weight(weights, hval=hval)
    # No user_id: non-deterministic assignment
    return _choose_by_weight(weights, hval=None)

