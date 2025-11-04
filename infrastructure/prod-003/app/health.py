from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from . import config
from .circuit_breaker import CircuitBreaker
from .db import ping

logger = logging.getLogger(__name__)


class HealthMonitor:
    def __init__(
        self,
        *,
        interval: float = config.HEALTHCHECK_INTERVAL,
        breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.interval = interval
        self.breaker = breaker
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="db-health-monitor", daemon=True)
        self._healthy = False

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: Optional[float] = None) -> None:
        self._stop.set()
        self._thread.join(timeout)

    @property
    def healthy(self) -> bool:
        return self._healthy

    def _run(self) -> None:
        while not self._stop.is_set():
            ok = ping()
            self._healthy = ok
            if ok:
                if self.breaker is not None:
                    self.breaker.record_success()
            else:
                if self.breaker is not None:
                    self.breaker.record_failure()
                if config.HEALTHCHECK_LOG_ERRORS:
                    logger.warning("Database healthcheck failed")
            self._stop.wait(self.interval)

