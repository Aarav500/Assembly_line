from __future__ import annotations
from typing import Dict, Optional, Tuple
from threading import Thread, Event, RLock
from datetime import datetime, timezone
import time

from sqlalchemy.exc import SQLAlchemyError

from config import settings
from db import registry
from router import choose_replica


class ReplicationOrchestrator:
    def __init__(self):
        self._stop_event = Event()
        self._lock = RLock()
        self._monitor_thread: Optional[Thread] = None
        self._heartbeat_thread: Optional[Thread] = None

        # Status maps
        self.replica_status: Dict[str, Dict] = {}
        # Preload known replicas from registry
        for name, meta in registry.replicas.items():
            self.replica_status[name] = {
                "region": meta.get("region"),
                "url": meta.get("url"),
                "healthy": False,
                "lag": None,
                "last_checked": None,
                "error": None,
            }

        self.primary_status: Dict[str, Optional[object]] = {
            "url": registry.primary_url,
            "healthy": False,
            "last_heartbeat": None,
            "last_checked": None,
            "error": None,
        }

    def start(self):
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_event.clear()
        self._heartbeat_thread = Thread(target=self._heartbeat_loop, name="heartbeat-updater", daemon=True)
        self._monitor_thread = Thread(target=self._monitor_loop, name="replica-monitor", daemon=True)
        self._heartbeat_thread.start()
        self._monitor_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2.0)

    def _heartbeat_loop(self):
        while not self._stop_event.is_set():
            try:
                registry.primary_heartbeat()
                with self._lock:
                    self.primary_status["healthy"] = True
                    self.primary_status["last_heartbeat"] = datetime.now(timezone.utc)
                    self.primary_status["last_checked"] = self.primary_status["last_heartbeat"]
                    self.primary_status["error"] = None
            except Exception as e:
                with self._lock:
                    self.primary_status["healthy"] = False
                    self.primary_status["error"] = str(e)
                    self.primary_status["last_checked"] = datetime.now(timezone.utc)
            self._stop_event.wait(timeout=settings.heartbeat_interval)

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            for name, meta in list(registry.replicas.items()):
                lag = None
                healthy = False
                error = None
                try:
                    ts = registry.read_heartbeat_timestamp(meta["engine"])
                    if ts is not None:
                        lag = max(0.0, (now - ts).total_seconds())
                        healthy = True
                    else:
                        # No heartbeat yet -> unknown, mark unhealthy
                        healthy = False
                        error = "no heartbeat"
                except Exception as e:
                    error = str(e)
                    healthy = False
                with self._lock:
                    st = self.replica_status.setdefault(name, {})
                    st.update({
                        "region": meta.get("region"),
                        "url": meta.get("url"),
                        "lag": lag,
                        "healthy": healthy,
                        "last_checked": now,
                        "error": error,
                    })
            self._stop_event.wait(timeout=settings.monitor_interval)

    def choose_read_replica(self, preferred_region: Optional[str]) -> Optional[Tuple[str, Dict]]:
        with self._lock:
            name = choose_replica(self.replica_status, preferred_region, settings.read_strategy, settings.max_replica_lag_seconds)
            if not name:
                return None
            return name, self.replica_status.get(name, {})

    def get_read_session(self, preferred_region: Optional[str] = None):
        choice = self.choose_read_replica(preferred_region)
        if not choice:
            return None, None, None
        name, meta = choice
        s, r = registry.get_replica_session_by_name(name)
        return s, name, r

    def promote_region(self, target_region: str) -> Dict:
        if not settings.promotion_allowed:
            raise PermissionError("Promotion not allowed by configuration")
        # Find a replica by region
        target_name = None
        for name, st in self.replica_status.items():
            if st.get("region") == target_region:
                target_name = name
                break
        if not target_name:
            raise ValueError(f"No replica found in region '{target_region}'")
        registry.promote_replica_to_primary(target_name)
        with self._lock:
            # Update primary status URL
            self.primary_status["url"] = registry.primary_url
        return {"promoted": target_name, "new_primary_url": registry.primary_url}

    def state(self) -> Dict:
        with self._lock:
            return {
                "primary": self.primary_status.copy(),
                "replicas": {name: st.copy() for name, st in self.replica_status.items()},
                "config": {
                    "region": settings.region,
                    "read_strategy": settings.read_strategy,
                    "max_replica_lag_seconds": settings.max_replica_lag_seconds,
                },
            }


orchestrator = ReplicationOrchestrator()

