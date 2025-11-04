import logging
import threading
import time

logger = logging.getLogger("graceful-resources")


class Heartbeat(threading.Thread):
    def __init__(self, interval: float = 5.0, name: str = "Heartbeat"):
        super().__init__(name=name, daemon=True)
        self._stop = threading.Event()
        self._interval = interval

    def run(self):
        logger.info("Heartbeat started with interval %.2fs", self._interval)
        while not self._stop.wait(self._interval):
            logger.debug("Heartbeat tick")
        logger.info("Heartbeat stopped")

    def stop(self):
        self._stop.set()
        self.join(timeout=self._interval + 1.0)

