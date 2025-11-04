import time
from dataclasses import dataclass, asdict
from typing import Optional


class BreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    success_threshold: int = 2
    recovery_timeout: float = 10.0  # seconds


class CircuitBreaker:
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self.state = BreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None

    def _now(self) -> float:
        return time.monotonic()

    def allow_request(self) -> bool:
        if self.state == BreakerState.OPEN:
            # If recovery timeout elapsed, transition to HALF_OPEN and allow a trial
            if self.last_failure_time is None:
                return False
            elapsed = self._now() - self.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self.state = BreakerState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        # CLOSED or HALF_OPEN -> allow
        return True

    def on_success(self):
        if self.state == BreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._close()
        elif self.state == BreakerState.CLOSED:
            # Reset failures on success in closed state
            self.failure_count = 0

    def on_failure(self):
        if self.state == BreakerState.HALF_OPEN:
            # Any failure in HALF_OPEN trips to OPEN immediately
            self._open()
            return

        self.failure_count += 1
        if self.failure_count >= self.config.failure_threshold:
            self._open()

    def _open(self):
        self.state = BreakerState.OPEN
        self.last_failure_time = self._now()
        self.opened_at = self.last_failure_time

    def _close(self):
        self.state = BreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None

    def to_dict(self):
        d = {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.config.failure_threshold,
            "success_threshold": self.config.success_threshold,
            "recovery_timeout": self.config.recovery_timeout,
            "last_failure_time": self.last_failure_time,
            "opened_at": self.opened_at,
        }
        return d

