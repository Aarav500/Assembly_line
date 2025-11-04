import logging
import random
import threading
import time
from functools import wraps
from typing import Callable, Iterable, Type

from config import Config


def retry(
    retries: int | None = None,
    backoff_factor: float | None = None,
    jitter: float | None = None,
    retry_on: Iterable[Type[BaseException]] = (Exception,),
    logger_name: str = "app.recovery",
):
    cfg = Config()
    max_retries = cfg.RETRY_DEFAULTS_RETRIES if retries is None else retries
    backoff = cfg.RETRY_DEFAULTS_BACKOFF if backoff_factor is None else backoff_factor
    jitter = cfg.RETRY_DEFAULTS_JITTER if jitter is None else jitter

    retry_on_tuple = tuple(retry_on)
    log = logging.getLogger(logger_name)

    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            attempts = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except retry_on_tuple as e:
                    if attempts >= max_retries:
                        log.error(
                            "retry exhausted",
                            extra={"extra": {"function": fn.__name__, "attempts": attempts, "error": str(e)}},
                        )
                        raise
                    sleep_for = (backoff * (2 ** attempts)) + random.uniform(0, jitter)
                    log.warning(
                        "retrying after error",
                        extra={
                            "extra": {
                                "function": fn.__name__,
                                "attempt": attempts + 1,
                                "sleep_s": round(sleep_for, 3),
                                "error": str(e),
                            }
                        },
                    )
                    time.sleep(max(0.0, sleep_for))
                    attempts += 1
        return wrapper

    return decorator


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: Iterable[Type[BaseException]] = (Exception,),
        logger_name: str = "app.circuit",
    ):
        self.name = name
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout = float(recovery_timeout)
        self.expected_exceptions = tuple(expected_exceptions)
        self.logger = logging.getLogger(logger_name)

        self._lock = threading.Lock()
        self._state = "closed"  # closed | open | half-open
        self._failures = 0
        self._opened_at = 0.0

    def _transition_to_open(self):
        self._state = "open"
        self._opened_at = time.time()
        self.logger.error("circuit open", extra={"extra": {"name": self.name}})

    def _transition_to_half_open(self):
        self._state = "half-open"
        self.logger.info("circuit half-open", extra={"extra": {"name": self.name}})

    def _transition_to_closed(self):
        self._state = "closed"
        self._failures = 0
        self._opened_at = 0.0
        self.logger.info("circuit closed", extra={"extra": {"name": self.name}})

    def __call__(self, fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            with self._lock:
                if self._state == "open":
                    if time.time() - self._opened_at >= self.recovery_timeout:
                        self._transition_to_half_open()
                    else:
                        raise RuntimeError(f"circuit '{self.name}' is open")

            try:
                result = fn(*args, **kwargs)
            except self.expected_exceptions as e:
                with self._lock:
                    self._failures += 1
                    if self._state in ("closed", "half-open") and self._failures >= self.failure_threshold:
                        self._transition_to_open()
                self.logger.warning(
                    "circuit captured failure",
                    extra={"extra": {"name": self.name, "failures": self._failures, "error": str(e)}},
                )
                raise
            else:
                with self._lock:
                    if self._state == "half-open":
                        self._transition_to_closed()
                    else:
                        self._failures = 0
                return result

        return wrapper

