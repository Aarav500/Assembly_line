import json
import logging
import os
import signal
import socket
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger("health")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Global state
_start_time = time.time()
_shutting_down = threading.Event()
_startup_complete = threading.Event()
_inflight_lock = threading.Lock()
_inflight_requests = 0
_liveness_failed = threading.Event()

# Config
_STARTUP_REQUIRE_DEPENDENCIES = True
_READINESS_REQUIRE_DEPENDENCIES = True
_STARTUP_TIMEOUT_SEC = None  # optional timeout to mark startup even if deps fail (None = never force)
_STARTUP_CHECK_INTERVAL_SEC = 1.0
_GRACEFUL_SHUTDOWN_TIMEOUT_SEC = 30
_HTTP_TIMEOUT_SEC = 1.5
_TCP_TIMEOUT_SEC = 1.0
_SQLITE_TIMEOUT_SEC = 1.0


@dataclass
class CheckResult:
    ok: bool
    message: str = ""
    extra: Optional[Dict] = None


@dataclass
class Dependency:
    name: str
    kind: str
    check: Callable[[], CheckResult]


_dependencies: List[Dependency] = []


def request_started() -> None:
    global _inflight_requests
    with _inflight_lock:
        _inflight_requests += 1


def request_finished() -> None:
    global _inflight_requests
    with _inflight_lock:
        _inflight_requests -= 1 if _inflight_requests > 0 else 0


def uptime_sec() -> float:
    return max(0.0, time.time() - _start_time)


# -------------------- Dependency helpers --------------------

def _check_http_url(url: str) -> CheckResult:
    req = Request(url=url, method="GET")
    try:
        with urlopen(req, timeout=_HTTP_TIMEOUT_SEC) as resp:
            code = resp.getcode()
            ok = 200 <= code < 400
            return CheckResult(ok=ok, message=f"HTTP {code}")
    except HTTPError as e:
        return CheckResult(ok=False, message=f"HTTPError {e.code}")
    except URLError as e:
        return CheckResult(ok=False, message=f"URLError {e.reason}")
    except Exception as e:
        return CheckResult(ok=False, message=f"Exception {type(e).__name__}: {e}")


def _check_tcp_endpoint(endpoint: str) -> CheckResult:
    host, _, port_str = endpoint.rpartition(":")
    try:
        port = int(port_str)
    except ValueError:
        return CheckResult(ok=False, message=f"Invalid port in endpoint: {endpoint}")
    if not host:
        return CheckResult(ok=False, message=f"Invalid host in endpoint: {endpoint}")
    try:
        with socket.create_connection((host, port), timeout=_TCP_TIMEOUT_SEC):
            return CheckResult(ok=True, message="connect ok")
    except Exception as e:
        return CheckResult(ok=False, message=f"connect failed: {e}")


def _check_sqlite(path: str) -> CheckResult:
    try:
        conn = sqlite3.connect(path, timeout=_SQLITE_TIMEOUT_SEC)
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchall()
            return CheckResult(ok=True, message="query ok")
        finally:
            conn.close()
    except Exception as e:
        return CheckResult(ok=False, message=f"sqlite error: {e}")


# -------------------- Public API --------------------

def add_dependency(name: str, kind: str, check_fn: Callable[[], CheckResult]) -> None:
    _dependencies.append(Dependency(name=name, kind=kind, check=check_fn))


def init_from_env() -> None:
    global _STARTUP_REQUIRE_DEPENDENCIES, _READINESS_REQUIRE_DEPENDENCIES
    global _STARTUP_TIMEOUT_SEC, _GRACEFUL_SHUTDOWN_TIMEOUT_SEC
    global _HTTP_TIMEOUT_SEC, _TCP_TIMEOUT_SEC, _SQLITE_TIMEOUT_SEC

    _STARTUP_REQUIRE_DEPENDENCIES = _env_bool("HEALTHCHECK_STARTUP_REQUIRE_DEPENDENCIES", True)
    _READINESS_REQUIRE_DEPENDENCIES = _env_bool("HEALTHCHECK_READINESS_REQUIRE_DEPENDENCIES", True)

    _STARTUP_TIMEOUT_SEC = _env_float("HEALTHCHECK_STARTUP_FORCE_READY_AFTER_SEC", None)
    _GRACEFUL_SHUTDOWN_TIMEOUT_SEC = int(os.environ.get("GRACEFUL_SHUTDOWN_TIMEOUT_SEC", "30"))

    _HTTP_TIMEOUT_SEC = float(os.environ.get("HEALTHCHECK_HTTP_TIMEOUT_SEC", "1.5"))
    _TCP_TIMEOUT_SEC = float(os.environ.get("HEALTHCHECK_TCP_TIMEOUT_SEC", "1.0"))
    _SQLITE_TIMEOUT_SEC = float(os.environ.get("HEALTHCHECK_SQLITE_TIMEOUT_SEC", "1.0"))

    # Discover dependencies from environment
    http_urls = _split_env("DEP_HTTP_URLS")
    for url in http_urls:
        add_dependency(name=f"http:{url}", kind="http", check_fn=lambda u=url: _check_http_url(u))

    tcp_eps = _split_env("DEP_TCP_ENDPOINTS")
    for ep in tcp_eps:
        add_dependency(name=f"tcp:{ep}", kind="tcp", check_fn=lambda e=ep: _check_tcp_endpoint(e))

    sqlite_paths = _split_env("DEP_SQLITE_PATHS")
    for path in sqlite_paths:
        add_dependency(name=f"sqlite:{path}", kind="sqlite", check_fn=lambda p=path: _check_sqlite(p))

    # Start background thread to mark startup when ready
    t = threading.Thread(target=_startup_watcher, name="startup-watcher", daemon=True)
    t.start()


def register_signal_handlers() -> None:
    def _on_signal(signum, frame):
        if not _shutting_down.is_set():
            logger.info(f"Received signal %s, initiating graceful shutdown", signum)
            _shutting_down.set()
            # Spawn a thread to log drain progress
            threading.Thread(target=_drain_logger, name="drain-logger", daemon=True).start()

    try:
        signal.signal(signal.SIGTERM, _on_signal)
        signal.signal(signal.SIGINT, _on_signal)
    except Exception as e:
        logger.warning("Unable to register signal handlers: %s", e)


def _drain_logger():
    deadline = time.time() + _GRACEFUL_SHUTDOWN_TIMEOUT_SEC
    while time.time() < deadline:
        with _inflight_lock:
            in_flight = _inflight_requests
        logger.info("Draining: in-flight=%s, remaining=%ss", in_flight, max(0, int(deadline - time.time())))
        if in_flight == 0:
            logger.info("No in-flight requests remaining. Safe to terminate.")
            break
        time.sleep(1.0)


def _startup_watcher():
    """Marks startup complete when allowed conditions are met."""
    if not _STARTUP_REQUIRE_DEPENDENCIES and not _dependencies:
        _startup_complete.set()
        logger.info("Startup complete (no dependencies required)")
        return

    start = time.time()
    while True:
        all_ok = True
        if _STARTUP_REQUIRE_DEPENDENCIES:
            for dep in _dependencies:
                res = dep.check()
                if not res.ok:
                    all_ok = False
                    break
        if all_ok:
            _startup_complete.set()
            logger.info("Startup complete (dependencies healthy)")
            return
        if _STARTUP_TIMEOUT_SEC is not None and time.time() - start >= _STARTUP_TIMEOUT_SEC:
            _startup_complete.set()
            logger.warning("Startup marked complete due to timeout (dependencies not all healthy)")
            return
        time.sleep(_STARTUP_CHECK_INTERVAL_SEC)


def check_liveness() -> Tuple[bool, Dict]:
    ok = not _liveness_failed.is_set()
    info = {
        "status": "ok" if ok else "fail",
        "shutting_down": _shutting_down.is_set(),
        "uptime_sec": int(uptime_sec()),
    }
    return ok, info


def check_readiness() -> Tuple[bool, Dict]:
    if _shutting_down.is_set():
        info = {
            "status": "fail",
            "reason": "shutting_down",
            "in_flight": _current_inflight(),
            "uptime_sec": int(uptime_sec()),
            "dependencies": {},
        }
        return False, info

    deps_ok, deps_details = _run_dependencies() if _READINESS_REQUIRE_DEPENDENCIES else (True, {})
    ok = deps_ok and (_startup_complete.is_set() or not _STARTUP_REQUIRE_DEPENDENCIES)

    info = {
        "status": "ok" if ok else "fail",
        "uptime_sec": int(uptime_sec()),
        "dependencies": deps_details,
    }
    return ok, info


def check_startup() -> Tuple[bool, Dict]:
    ok = _startup_complete.is_set()
    info = {
        "status": "ok" if ok else "fail",
        "uptime_sec": int(uptime_sec()),
        "required_dependencies": _STARTUP_REQUIRE_DEPENDENCIES,
    }
    return ok, info


def _run_dependencies() -> Tuple[bool, Dict[str, Dict]]:
    overall_ok = True
    details: Dict[str, Dict] = {}
    for dep in _dependencies:
        try:
            res = dep.check()
            details[dep.name] = {
                "kind": dep.kind,
                "ok": res.ok,
                "message": res.message,
            }
            if not res.ok:
                overall_ok = False
        except Exception as e:
            details[dep.name] = {
                "kind": dep.kind,
                "ok": False,
                "message": f"check raised: {e}",
            }
            overall_ok = False
    return overall_ok, details


def _current_inflight() -> int:
    with _inflight_lock:
        return _inflight_requests


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: Optional[float]) -> Optional[float]:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _split_env(name: str) -> List[str]:
    v = os.environ.get(name, "").strip()
    if not v:
        return []
    parts = [p.strip() for p in v.split(",")]
    return [p for p in parts if p]

