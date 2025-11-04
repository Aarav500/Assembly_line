from typing import List, Optional


def percentile(values: List[float], p: float) -> Optional[float]:
    """
    Compute percentile p in [0,1] using linear interpolation
    Returns None if values is empty.
    """
    n = len(values)
    if n == 0:
        return None
    if p <= 0:
        return min(values)
    if p >= 1:
        return max(values)
    xs = sorted(values)
    idx = p * (n - 1)
    i = int(idx)
    frac = idx - i
    if i + 1 < n:
        return xs[i] * (1 - frac) + xs[i + 1] * frac
    return xs[i]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def round_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return round(value / step) * step


def ceil_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    import math
    return math.ceil(value / step) * step


def floor_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    import math
    return math.floor(value / step) * step

