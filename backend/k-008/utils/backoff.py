import random


def compute_delay(attempt: int, base: float, factor: float, max_delay: float, jitter: str = "full") -> float:
    """Compute exponential backoff delay with optional jitter.

    attempt: 1-based attempt number
    base: initial delay in seconds
    factor: exponential multiplier
    max_delay: cap on delay
    jitter: 'full' (0..delay), 'equal' (delay/2..delay), 'none' (exact delay)
    """
    if attempt < 1:
        attempt = 1
    delay = base * (factor ** (attempt - 1))
    if delay > max_delay:
        delay = max_delay
    if jitter == "none":
        return max(0.0, delay)
    if jitter == "equal":
        lo = delay / 2.0
        hi = delay
        return max(0.0, random.uniform(lo, hi))
    # default full jitter
    return max(0.0, random.uniform(0.0, delay))

