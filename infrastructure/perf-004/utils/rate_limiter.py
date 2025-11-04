import threading
import time


class TokenBucket:
    """
    Thread-safe token bucket rate limiter.
    rate: tokens per second
    capacity: bucket size (burst)
    """

    def __init__(self, rate: float, capacity: float):
        self.rate = float(rate)
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        delta = now - self._last
        self._last = now
        self._tokens = min(self.capacity, self._tokens + delta * self.rate)

    def try_acquire(self) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def acquire(self, timeout: float = None) -> bool:
        deadline = None if timeout is None else (time.monotonic() + timeout)
        while True:
            if self.try_acquire():
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            # Sleep proportionally to missing tokens but cap small sleep
            with self._lock:
                need = max(0.0, 1.0 - self._tokens)
                wait = min(0.05, need / self.rate if self.rate > 0 else 0.05)
            time.sleep(wait if wait > 0 else 0.01)

