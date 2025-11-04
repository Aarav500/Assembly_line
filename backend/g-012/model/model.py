import math
import random
from typing import Dict, Any


class SimpleModel:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        # Pre-generate weights for hash buckets to be deterministic
        self._weights = {}
        self.bias = 0.0

    def _weight_for_key(self, key: str) -> float:
        if key not in self._weights:
            # Deterministic pseudo-random based on key
            rnd = random.Random(hash(key) & 0xffffffff)
            self._weights[key] = (rnd.random() - 0.5) * 0.2  # small weight
        return self._weights[key]

    def predict(self, features: Dict[str, Any]) -> float:
        z = self.bias
        for k, v in features.items():
            if isinstance(v, bool) or v is None:
                continue
            try:
                val = float(v)
                w = self._weight_for_key(f'n:{k}')
                z += w * val
            except Exception:
                # treat as categorical hashed into few buckets
                bucket = hash(str(v)) % 8
                w = self._weight_for_key(f'c:{k}:{bucket}')
                z += w
        # Sigmoid
        p = 1.0 / (1.0 + math.exp(-z))
        # Bound strictly within (0,1)
        p = min(max(p, 1e-6), 1 - 1e-6)
        return p

