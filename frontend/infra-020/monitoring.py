import threading
import time
import socket
import requests
import yaml
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from breaker import CircuitBreaker, CircuitBreakerConfig


DEFAULT_INTERVAL = 15.0
DEFAULT_TIMEOUT = 3.0
DEFAULT_STALENESS = 30.0


def utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class Dependency:
    def __init__(self, cfg: Dict[str, Any]):
        self.name: str = cfg.get("name") or cfg.get("url") or cfg.get("host", "unknown")
        self.type: str = cfg.get("type", "http").lower()
        self.critical: bool = bool(cfg.get("critical", False))
        self.interval: float = float(cfg.get("interval", DEFAULT_INTERVAL))
        self.timeout: float = float(cfg.get("timeout", DEFAULT_TIMEOUT))

        # HTTP specific
        self.method: str = cfg.get("method", "GET").upper()
        self.url: Optional[str] = cfg.get("url")
        self.headers: Dict[str, str] = cfg.get("headers", {})
        self.expected_status_min: int = int(cfg.get("expected_status_min", 200))
        self.expected_status_max: int = int(cfg.get("expected_status_max", 399))
        self.payload: Any = cfg.get("payload")

        # TCP specific
        self.host: Optional[str] = cfg.get("host")
        self.port: Optional[int] = cfg.get("port")

        bcfg = cfg.get("breaker", {}) or {}
        self.breaker = CircuitBreaker(
            self.name,
            CircuitBreakerConfig(
                failure_threshold=int(bcfg.get("failure_threshold", 3)),
                success_threshold=int(bcfg.get("success_threshold", 2)),
                recovery_timeout=float(bcfg.get("recovery_timeout", 10.0)),
            ),
        )

        # Runtime state
        self.last_check_at: Optional[float] = None
        self.last_ok: Optional[bool] = None
        self.last_latency_ms: Optional[float] = None
        self.last_error: Optional[str] = None
        self.last_status_code: Optional[int] = None
        self.last_state_label: Optional[str] = None

        self._lock = threading.Lock()

    def _check_http(self) -> (bool, Optional[int], Optional[str], Optional[float]):
        start = time.monotonic()
        try:
            resp = requests.request(
                self.method,
                self.url,
                headers=self.headers,
                json=self.payload if isinstance(self.payload, (dict, list)) else None,
                data=None if isinstance(self.payload, (dict, list)) else self.payload,
                timeout=self.timeout,
            )
            latency_ms = (time.monotonic() - start) * 1000.0
            code = resp.status_code
            ok = self.expected_status_min <= code <= self.expected_status_max
            err = None if ok else f"HTTP {code}"
            return ok, code, err, latency_ms
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000.0
            return False, None, str(e), latency_ms

    def _check_tcp(self) -> (bool, Optional[int], Optional[str], Optional[float]):
        start = time.monotonic()
        try:
            with socket.create_connection((self.host, int(self.port)), timeout=self.timeout):
                latency_ms = (time.monotonic() - start) * 1000.0
                return True, None, None, latency_ms
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000.0
            return False, None, str(e), latency_ms

    def check(self):
        allowed = self.breaker.allow_request()
        state_label = None
        ok = False
        code = None
        err = None
        latency_ms = None

        if not allowed:
            # Breaker is OPEN and recovery timeout not reached
            state_label = "SKIPPED_OPEN"
            ok = False
        else:
            if self.type == "http":
                ok, code, err, latency_ms = self._check_http()
            elif self.type == "tcp":
                ok, code, err, latency_ms = self._check_tcp()
            else:
                ok, code, err, latency_ms = False, None, f"Unsupported type: {self.type}", None

            if ok:
                self.breaker.on_success()
                state_label = "UP"
            else:
                self.breaker.on_failure()
                state_label = "DOWN"
                if self.breaker.state == "OPEN":
                    state_label = "TRIPPED_OPEN"
                elif self.breaker.state == "HALF_OPEN":
                    state_label = "HALF_OPEN_FAIL"

        with self._lock:
            self.last_check_at = time.monotonic()
            self.last_ok = ok
            self.last_latency_ms = latency_ms
            self.last_error = err
            self.last_status_code = code
            self.last_state_label = state_label

    def is_due(self, now_mono: float) -> bool:
        with self._lock:
            if self.last_check_at is None:
                return True
            return (now_mono - self.last_check_at) >= self.interval

    def is_stale(self, staleness_seconds: float, now_mono: Optional[float] = None) -> bool:
        with self._lock:
            if self.last_check_at is None:
                return True
            nm = now_mono if now_mono is not None else time.monotonic()
            return (nm - self.last_check_at) > staleness_seconds

    def get_public_status(self) -> Dict[str, Any]:
        with self._lock:
            last_checked_iso = None
            if self.last_check_at is not None:
                # Approximate wall time by subtracting monotonic delta from now
                now_wall = datetime.now(timezone.utc)
                delta = time.monotonic() - self.last_check_at
                checked_at = now_wall - timedelta_seconds(delta)
                last_checked_iso = checked_at.isoformat()

            d = {
                "name": self.name,
                "type": self.type,
                "critical": self.critical,
                "endpoint": self.url if self.type == "http" else f"{self.host}:{self.port}",
                "status": self.last_state_label,
                "ok": self.last_ok,
                "last_checked_at": last_checked_iso,
                "latency_ms": self.last_latency_ms,
                "http_status": self.last_status_code if self.type == "http" else None,
                "error": self.last_error,
                "breaker": self.breaker.to_dict(),
            }
            return d


def timedelta_seconds(seconds: float) -> datetime.timedelta:
    from datetime import timedelta
    return timedelta(seconds=seconds)


class DependencyManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.service_name = "health-check-service"
        self.refresh_seconds = 5.0
        self.staleness_seconds = DEFAULT_STALENESS
        self._load_config()

        self._deps: List[Dependency] = []
        for dcfg in self._config_deps:
            self._deps.append(Dependency(dcfg))

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        self.service_name = (cfg.get("service", {}) or {}).get("name", self.service_name)
        self.refresh_seconds = float((cfg.get("service", {}) or {}).get("refresh_seconds", 5))
        self.staleness_seconds = float((cfg.get("service", {}) or {}).get("staleness_seconds", DEFAULT_STALENESS))
        self._config_deps = cfg.get("dependencies", []) or []

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="dependency-monitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_loop(self):
        while self._running:
            now_mono = time.monotonic()
            for dep in self._deps:
                try:
                    if dep.is_due(now_mono):
                        dep.check()
                except Exception:
                    # Ensure the loop continues even if one dependency raises unexpectedly
                    pass
            time.sleep(0.5)

    def _dependencies_status(self) -> List[Dict[str, Any]]:
        return [d.get_public_status() for d in self._deps]

    def _calculate_overall(self, deps_status: List[Dict[str, Any]]):
        any_critical_down = any(
            (ds.get("critical") and not ds.get("ok")) for ds in deps_status
        )
        any_noncritical_down = any(
            (not ds.get("critical") and not ds.get("ok")) for ds in deps_status
        )
        if any_critical_down:
            return "DOWN"
        if any_noncritical_down:
            return "DEGRADED"
        return "UP"

    def get_overall_status(self, force_check_if_stale: bool = False) -> Dict[str, Any]:
        if force_check_if_stale:
            # Synchronously check stale critical dependencies to avoid serving stale readiness
            for dep in self._deps:
                if dep.critical and dep.is_stale(self.staleness_seconds):
                    try:
                        dep.check()
                    except Exception:
                        pass

        deps = self._dependencies_status()
        overall = self._calculate_overall(deps)
        return {
            "service": self.service_name,
            "time": utc_now_str(),
            "overall_status": overall,
            "dependencies": deps,
        }

