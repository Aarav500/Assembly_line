import json
import os
import threading
import time
from typing import Dict, Any, Optional


DEFAULT_STATE = {
    "stable_version": "v1",
    "canary_version": "v2",
    "canary_weight": 0.1,
    "auto_canary_enabled": True,
    "thresholds": {
        "min_requests": 100,
        "canary_error_rate_absolute_max": 0.15,
        "relative_error_rate_increase_pct_allowed": 50.0,
        "canary_latency_p95_ms_max": 800.0,
        "evaluation_interval_sec": 15.0,
    },
    "last_action": None,
    "last_action_reason": None,
    "last_updated": None,
}


class CanaryController:
    def __init__(self, state_path: str = "state.json"):
        self.state_path = state_path
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_stop = threading.Event()
        self._metrics = None
        if not os.path.exists(self.state_path):
            self._write_state(DEFAULT_STATE)
        self._state = self._read_state()

    def _read_state(self) -> Dict[str, Any]:
        with self._lock:
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                # If corrupt, reset to default
                return DEFAULT_STATE.copy()

    def _write_state(self, state: Dict[str, Any]):
        with self._lock:
            state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            tmp_path = self.state_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp_path, self.state_path)
            self._state = state

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def set_canary_weight(self, weight: float):
        if weight is None:
            raise ValueError("weight required")
        if weight < 0 or weight > 1:
            raise ValueError("weight must be between 0 and 1")
        state = self.get_state()
        if not state.get("canary_version"):
            raise ValueError("no canary_version set")
        state["canary_weight"] = float(weight)
        state["last_action"] = "set_weight"
        state["last_action_reason"] = None
        self._write_state(state)

    def set_canary_version(self, version: Optional[str]):
        state = self.get_state()
        state["canary_version"] = version
        if version is None:
            state["canary_weight"] = 0.0
        state["last_action"] = "set_canary_version"
        state["last_action_reason"] = None
        self._write_state(state)

    def promote_canary(self):
        state = self.get_state()
        canary = state.get("canary_version")
        if not canary:
            raise ValueError("no canary to promote")
        state["stable_version"] = canary
        state["canary_version"] = None
        state["canary_weight"] = 0.0
        state["last_action"] = "promote"
        state["last_action_reason"] = "manual"
        self._write_state(state)

    def rollback_canary(self, reason: str = "auto"):
        state = self.get_state()
        if not state.get("canary_version"):
            return
        state["canary_weight"] = 0.0
        state["last_action"] = "rollback"
        state["last_action_reason"] = reason
        self._write_state(state)

    def set_thresholds(self, thresholds: Dict[str, Any]):
        state = self.get_state()
        t = state.get("thresholds", {}).copy()
        t.update({k: v for k, v in thresholds.items() if v is not None})
        state["thresholds"] = t
        state["last_action"] = "set_thresholds"
        self._write_state(state)

    def toggle_auto(self, enabled: bool):
        state = self.get_state()
        state["auto_canary_enabled"] = bool(enabled)
        state["last_action"] = "toggle_auto"
        self._write_state(state)

    def start_monitor(self, metrics):
        self._metrics = metrics
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, name="canary-monitor", daemon=True)
        self._monitor_thread.start()

    def stop_monitor(self):
        self._monitor_stop.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)

    def _monitor_loop(self):
        while not self._monitor_stop.is_set():
            try:
                state = self.get_state()
                interval = float(state.get("thresholds", {}).get("evaluation_interval_sec", 15.0))
                if state.get("auto_canary_enabled"):
                    self._evaluate_once()
            except Exception:
                # ignore errors in monitor loop
                pass
            finally:
                time.sleep(max(3.0, min(120.0, interval)))

    def _evaluate_once(self):
        if not self._metrics:
            return
        state = self.get_state()
        canary = state.get("canary_version")
        weight = float(state.get("canary_weight", 0.0))
        stable = state.get("stable_version")
        if not canary or weight <= 0.0:
            return
        snap = self._metrics.snapshot()
        pv = snap.get("per_version", {})
        canary_stats = pv.get(canary)
        stable_stats = pv.get(stable)
        if not canary_stats:
            return
        min_requests = int(state.get("thresholds", {}).get("min_requests", 100))
        if canary_stats.get("total_requests", 0) < min_requests:
            return
        canary_err_rate = canary_stats.get("error_rate", 0.0)
        canary_p95 = canary_stats.get("latency_ms", {}).get("p95") or 0.0
        stable_err_rate = stable_stats.get("error_rate", 0.0) if stable_stats else 0.0

        abs_err_max = float(state.get("thresholds", {}).get("canary_error_rate_absolute_max", 0.15))
        rel_increase_allowed = float(state.get("thresholds", {}).get("relative_error_rate_increase_pct_allowed", 50.0))
        p95_max = float(state.get("thresholds", {}).get("canary_latency_p95_ms_max", 800.0))

        reason = None
        # Absolute threshold
        if canary_err_rate > abs_err_max:
            reason = f"canary error rate {canary_err_rate:.3f} > abs max {abs_err_max:.3f}"
        # Relative increase
        elif stable_err_rate > 0:
            increase_pct = ((canary_err_rate - stable_err_rate) / stable_err_rate) * 100.0
            if increase_pct > rel_increase_allowed:
                reason = f"error rate increase {increase_pct:.1f}% > allowed {rel_increase_allowed:.1f}%"
        # Latency p95 absolute
        if reason is None and canary_p95 > p95_max:
            reason = f"canary p95 {canary_p95:.1f}ms > max {p95_max:.1f}ms"

        if reason:
            self.rollback_canary(reason=reason)


