import threading
import time
from typing import Dict, Optional

class LeaseManager:
    def __init__(self, vault_manager, check_interval: float = 5.0, renew_margin: float = 0.2):
        self.vault = vault_manager
        self.check_interval = check_interval
        self.renew_margin = renew_margin
        self._leases: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="LeaseManager", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def add(self, lease_id: str, lease_duration: int, renewable: bool, meta: Optional[Dict] = None):
        now = time.time()
        next_renew = now + max(1, int(lease_duration * (1.0 - self.renew_margin)))
        with self._lock:
            self._leases[lease_id] = {
                "lease_id": lease_id,
                "lease_duration": lease_duration,
                "renewable": renewable,
                "last_renewal": None,
                "next_renewal": next_renew,
                "failures": 0,
                "meta": meta or {},
            }

    def remove(self, lease_id: str):
        with self._lock:
            self._leases.pop(lease_id, None)

    def get(self, lease_id: str) -> Optional[Dict]:
        with self._lock:
            return self._leases.get(lease_id)

    def count(self) -> int:
        with self._lock:
            return len(self._leases)

    def snapshot(self):
        with self._lock:
            # return a shallow copy suitable for JSON
            return list(self._leases.values())

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                # swallow exceptions to keep the loop running
                pass
            self._stop.wait(self.check_interval)

    def _tick(self):
        now = time.time()
        to_renew = []
        with self._lock:
            for lease_id, item in list(self._leases.items()):
                if not item.get("renewable", False):
                    continue
                next_renewal = item.get("next_renewal", 0)
                if now >= next_renewal:
                    to_renew.append(lease_id)
        for lease_id in to_renew:
            try:
                # Renew with the same increment as original duration if possible
                item = self.get(lease_id)
                increment = item.get("lease_duration") if item else None
                resp = self.vault.renew_lease(lease_id=lease_id, increment=increment)
                new_duration = resp.get("lease_duration") or resp.get("auth", {}).get("lease_duration") or increment or 60
                now2 = time.time()
                next_renew = now2 + max(1, int(new_duration * (1.0 - self.renew_margin)))
                with self._lock:
                    if lease_id in self._leases:
                        self._leases[lease_id]["lease_duration"] = new_duration
                        self._leases[lease_id]["last_renewal"] = now2
                        self._leases[lease_id]["next_renewal"] = next_renew
                        self._leases[lease_id]["failures"] = 0
            except Exception:
                with self._lock:
                    if lease_id in self._leases:
                        self._leases[lease_id]["failures"] = self._leases[lease_id].get("failures", 0) + 1
                        # If too many failures, drop the lease
                        if self._leases[lease_id]["failures"] >= 3:
                            self._leases.pop(lease_id, None)

