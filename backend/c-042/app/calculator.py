import re
from typing import Optional


def safe_divide(a: float, b: float, default: Optional[float] = None) -> float:
    """Divide a by b. If b is zero, return default if provided else 0.

    This function is intentionally simple and a candidate for common mutation operators
    like equality flips and constant changes.
    """
    if b == 0:
        return default if default is not None else 0
    return a / b


def clamp(n: float, lo: float, hi: float) -> float:
    """Clamp n to the inclusive range [lo, hi]. If bounds are reversed, fix them."""
    if lo > hi:
        lo, hi = hi, lo
    if n < lo:
        return lo
    if n > hi:
        return hi
    return n


def is_palindrome(s: str) -> bool:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", s).lower()
    return cleaned == cleaned[::-1]


def sign(n: float) -> int:
    if n > 0:
        return 1
    elif n < 0:
        return -1
    else:
        return 0

