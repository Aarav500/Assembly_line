from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar, Generic

T = TypeVar("T")


class CircuitBreakerOpen(Exception):
    def __init__(self, message: str = "Circuit breaker is OPEN; operation blocked") -> None:
        super().__init__(message)


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_success: int = 2


class CircuitBreaker(Generic[T]):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, name: str, config: CircuitBreakerConfig) -> None:
        self._name = name
        self._cfg = config
        self._state = CircuitBreaker.CLOSED
        self._fail_count = 0
        self._state_since = time.monotonic()
        self._half_open_success = 0
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitBreaker.HALF_OPEN:
                self._half_open_success += 1
                if self._half_open_success >= self._cfg.half_open_max_success:
                    self._to_closed()
            elif self._state == CircuitBreaker.CLOSED:
                # Reset failure streak on success in closed
                self._fail_count = 0

    def record_failure(self) -> None:
        with self._lock:
            if self._state == CircuitBreaker.HALF_OPEN:
                self._to_open()
                return
            if self._state == CircuitBreaker.CLOSED:
                self._fail_count += 1
                if self._fail_count >= self._cfg.failure_threshold:
                    self._to_open()

    def _to_open(self) -> None:
        self._state = CircuitBreaker.OPEN
        self._state_since = time.monotonic()
        self._half_open_success = 0

    def _to_half_open(self) -> None:
        self._state = CircuitBreaker.HALF_OPEN
        self._state_since = time.monotonic()
        self._half_open_success = 0

    def _to_closed(self) -> None:
        self._state = CircuitBreaker.CLOSED
        self._state_since = time.monotonic()
        self._fail_count = 0
        self._half_open_success = 0

    def _can_pass(self) -> bool:
        now = time.monotonic()
        if self._state == CircuitBreaker.OPEN:
            if (now - self._state_since) >= self._cfg.recovery_timeout:
                # Allow a trial
                self._to_half_open()
                return True
            return False
        return True

    def execute(
        self,
        operation: Callable[[], T],
        *,
        fallback: Optional[Callable[[], T]] = None,
        on_open: Optional[Callable[[str], None]] = None,
    ) -> T:
        if not self._can_pass():
            if on_open:
                on_open(self._name)
            if fallback is not None:
                return fallback()
            raise CircuitBreakerOpen()

        try:
            result = operation()
        except Exception:
            self.record_failure()
            raise
        else:
            self.record_success()
            return result

