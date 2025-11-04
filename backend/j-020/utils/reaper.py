import threading
import time
from typing import Optional

from services.sandbox_service import SandboxService

class ReaperThread(threading.Thread):
    def __init__(self, service: SandboxService, interval_seconds: int = 30):
        super().__init__(daemon=True)
        self.service = service
        self.interval = max(5, int(interval_seconds or 30))
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                self.service.reap_expired()
            except Exception:
                pass
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()

_reaper: Optional[ReaperThread] = None

def start_reaper(service: SandboxService, interval_seconds: int = 30):
    global _reaper
    if _reaper is None:
        _reaper = ReaperThread(service, interval_seconds)
        _reaper.start()
    return _reaper

