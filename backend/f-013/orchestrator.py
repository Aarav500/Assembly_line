from __future__ import annotations
import threading
import time
from typing import Any, Dict, List, Optional

from utils import load_config, setup_logger, utc_now_iso
from health_checks import run_check
from healer import run_heal


class Orchestrator:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = load_config(config_path)
        self.logger = setup_logger(self.config)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.state_lock = threading.Lock()
        self.status: Dict[str, Dict[str, Any]] = {}
        self.incidents: List[Dict[str, Any]] = []
        self.max_incidents = 200
        self.cooldown = int((self.config.get("healing", {}) or {}).get("cooldown_seconds", 300))
        self.dry_run = bool((self.config.get("healing", {}) or {}).get("dry_run", False))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, name="health-orchestrator", daemon=True)
        self._thread.start()
        self.logger.info("Health Orchestrator started")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        # initialize schedules
        last_run: Dict[str, float] = {}
        while not self._stop.is_set():
            cfg_checks = (self.config.get("checks") or {})
            now = time.time()
            for name, chk in cfg_checks.items():
                interval = int(chk.get("interval", 15))
                if now - last_run.get(name, 0) < interval:
                    continue
                last_run[name] = now
                try:
                    result = run_check(name, chk)
                except Exception as e:
                    result = {
                        "name": name,
                        "type": chk.get("type", "unknown"),
                        "status": "fail",
                        "message": f"check raised: {e}",
                        "metrics": {},
                        "timestamp": utc_now_iso(),
                    }
                self._update_status_and_maybe_heal(name, chk, result)
            time.sleep(1)

    def _update_status_and_maybe_heal(self, name: str, chk: Dict[str, Any], result: Dict[str, Any]):
        with self.state_lock:
            st = self.status.get(name) or {
                "last_result": None,
                "consecutive_failures": 0,
                "last_heal_time": 0,
                "last_heal_result": None,
            }
            self.status[name] = st
            st["last_result"] = result
            if result.get("status") == "pass":
                st["consecutive_failures"] = 0
                return
            st["consecutive_failures"] = int(st.get("consecutive_failures", 0)) + 1
            needed = int(chk.get("consecutive_failures", 1))
            if st["consecutive_failures"] < needed:
                return
            heal_action = chk.get("heal_action")
            if not heal_action:
                return
            now = time.time()
            if now - st.get("last_heal_time", 0) < self.cooldown:
                return
            # run heal
            self.logger.warning(f"Auto-heal triggered for {name}: action={heal_action} result={result.get('message')}")
        heal_params = chk.get("heal_params", {})
        heal_result = run_heal(heal_action, name, chk, heal_params, dry_run=self.dry_run)
        with self.state_lock:
            st = self.status[name]
            st["last_heal_time"] = time.time()
            st["last_heal_result"] = heal_result
            incident = {
                "time": utc_now_iso(),
                "check": name,
                "action": heal_action,
                "result": heal_result,
                "check_result": result,
            }
            self.incidents.append(incident)
            if len(self.incidents) > self.max_incidents:
                self.incidents = self.incidents[-self.max_incidents:]

    def manual_run_check(self, name: str) -> Dict[str, Any]:
        chk = (self.config.get("checks") or {}).get(name)
        if not chk:
            return {"error": f"unknown check {name}"}
        try:
            result = run_check(name, chk)
        except Exception as e:
            result = {"name": name, "status": "fail", "message": f"check raised: {e}", "timestamp": utc_now_iso()}
        self._update_status_and_maybe_heal(name, chk, result)
        return result

    def manual_heal(self, name: str, action: str | None = None, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        chk = (self.config.get("checks") or {}).get(name)
        if not chk:
            return {"error": f"unknown check {name}"}
        act = action or chk.get("heal_action")
        if not act:
            return {"error": f"no heal action configured for {name}"}
        res = run_heal(act, name, chk, params or chk.get("heal_params", {}), dry_run=self.dry_run)
        with self.state_lock:
            st = self.status.get(name) or {}
            st["last_heal_time"] = time.time()
            st["last_heal_result"] = res
            self.status[name] = st
            self.incidents.append({
                "time": utc_now_iso(),
                "check": name,
                "action": act,
                "result": res,
                "manual": True,
            })
            if len(self.incidents) > self.max_incidents:
                self.incidents = self.incidents[-self.max_incidents:]
        return res

    def overall_ready(self) -> Dict[str, Any]:
        # readiness: fail if any non-optional check currently failing
        failing: List[str] = []
        with self.state_lock:
            for name, st in self.status.items():
                lr = st.get("last_result") or {}
                optional = (self.config.get("checks") or {}).get(name, {}).get("optional", False)
                if lr.get("status") != "pass" and not optional:
                    failing.append(name)
        return {"status": "pass" if not failing else "fail", "failing": failing}

    def snapshot(self) -> Dict[str, Any]:
        with self.state_lock:
            snap = {k: v.copy() for k, v in self.status.items()}
        return snap

