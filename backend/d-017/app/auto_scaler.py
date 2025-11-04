import threading
import time

from .fleet import FleetManager


class AutoScaler:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.fm = FleetManager(db=db, config=config)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="AutoScaler", daemon=True)

    def start(self):
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self):
        interval = int(self.config.SCALE_INTERVAL_SECONDS)
        while not self._stop.is_set():
            try:
                self.fm.reconcile()
            except Exception:
                pass
            # Sleep with responsiveness to stop event
            for _ in range(interval):
                if self._stop.is_set():
                    break
                time.sleep(1)

