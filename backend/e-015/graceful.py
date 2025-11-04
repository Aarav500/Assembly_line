import logging
import os
import signal
import threading
import time
from typing import Optional

logger = logging.getLogger("spot.graceful")


class LifecycleManager:
    def __init__(self, grace_period_seconds: int = 110):
        self.grace_period = grace_period_seconds
        self.draining_event = threading.Event()
        self._exit_timer_started = False
        self._lock = threading.Lock()

    def is_draining(self) -> bool:
        return self.draining_event.is_set()

    def install_signal_handlers(self):
        def handle(sig, frame):
            src = f"signal:{signal.Signals(sig).name}"
            logger.warning("Received %s; initiating drain", src)
            self.initiate_draining(source=src)
        signal.signal(signal.SIGTERM, handle)
        signal.signal(signal.SIGINT, handle)

    def initiate_draining(self, source: Optional[str] = None):
        with self._lock:
            if not self.draining_event.is_set():
                logger.warning("Draining initiated (source=%s). New work will be rejected.", source)
                self.draining_event.set()
            if not self._exit_timer_started:
                self._exit_timer_started = True
                t = threading.Thread(target=self._exit_after_grace, name="ExitAfterGrace", daemon=True)
                t.start()

    def _exit_after_grace(self):
        # Give time for load balancer deregistration and in-flight job completion
        remaining = self.grace_period
        while remaining > 0:
            time.sleep(min(5, remaining))
            remaining -= 5
        logger.warning("Grace period elapsed; exiting now")
        # Ensure process exit; external supervisor should restart or terminate
        os._exit(0)

