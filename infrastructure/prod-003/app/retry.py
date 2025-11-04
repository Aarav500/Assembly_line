from __future__ import annotations

import logging
import random
import time
from typing import Callable, Iterable, TypeVar

from sqlalchemy.exc import DBAPIError, DisconnectionError, InterfaceError, OperationalError, TimeoutError

T = TypeVar("T")


def is_retryable_db_error(exc: Exception) -> bool:
    if isinstance(exc, (OperationalError, InterfaceError, DisconnectionError, TimeoutError)):
        return True
    if isinstance(exc, DBAPIError):
        try:
            if exc.connection_invalidated:
                return True
        except Exception:
            pass
        orig = getattr(exc, "orig", None)
        code = getattr(orig, "pgcode", None)
        if code in ("40001", "40P01"):
            return True
    return False


def call_with_retry(
    func: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.2,
    max_delay: float = 3.0,
    logger: logging.Logger | None = None,
    should_retry: Callable[[Exception], bool] = is_retryable_db_error,
) -> T:
    attempt = 1
    last_exc: Exception | None = None
    while attempt <= max_attempts:
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not should_retry(exc) or attempt >= max_attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            # Full jitter
            delay = random.uniform(0, delay)
            if logger:
                logger.warning(
                    "Transient DB error (attempt %s/%s), retrying in %.2fs: %s",
                    attempt,
                    max_attempts,
                    delay,
                    exc,
                )
            time.sleep(delay)
            attempt += 1
    assert last_exc is not None
    raise last_exc

