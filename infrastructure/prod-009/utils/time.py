import time


def now_ts() -> int:
    return int(time.time())


def ttl_from_deadline(deadline_ts: int) -> int:
    # seconds remaining to deadline
    delta = deadline_ts - now_ts()
    return max(0, delta)

