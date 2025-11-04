import random
from datetime import timedelta
import config


def compute_backoff_seconds(attempt_num: int) -> timedelta:
    base = config.BACKOFF_BASE_SECONDS
    cap = config.BACKOFF_MAX_SECONDS
    jitter = config.JITTER_SECONDS
    delay = min(cap, base * (2 ** max(0, attempt_num - 1)))
    delay += random.uniform(0, jitter)
    return timedelta(seconds=delay)

