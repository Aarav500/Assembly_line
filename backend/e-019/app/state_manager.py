import json
import os
import tempfile
import time
from typing import Any, Dict


DEFAULT_STATE = {
    "active_region": None,
    "last_failover_ts": None,
    "last_failover_reason": None,
    "last_dns_sync_ts": None,
    "simulated_outage": {"primary": False, "secondary": False},
}


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def load_state(path: str) -> Dict[str, Any]:
    _ensure_dir(path)
    if not os.path.exists(path):
        state = DEFAULT_STATE.copy()
        return state
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    # merge defaults
    state = DEFAULT_STATE.copy()
    state.update(data or {})
    # ensure nested defaults
    if "simulated_outage" not in state or not isinstance(state["simulated_outage"], dict):
        state["simulated_outage"] = {"primary": False, "secondary": False}
    if "primary" not in state["simulated_outage"]:
        state["simulated_outage"]["primary"] = False
    if "secondary" not in state["simulated_outage"]:
        state["simulated_outage"]["secondary"] = False
    return state


def save_state(path: str, state: Dict[str, Any]) -> None:
    _ensure_dir(path)
    # write atomically
    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix="state_", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(state, tmp, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def set_active_region(path: str, region: str, reason: str | None = None) -> Dict[str, Any]:
    state = load_state(path)
    state["active_region"] = region
    state["last_failover_ts"] = int(time.time())
    state["last_failover_reason"] = reason
    save_state(path, state)
    return state


def set_dns_sync(path: str) -> Dict[str, Any]:
    state = load_state(path)
    state["last_dns_sync_ts"] = int(time.time())
    save_state(path, state)
    return state


def set_simulated_outage(path: str, region_key: str, down: bool) -> Dict[str, Any]:
    state = load_state(path)
    if region_key not in ("primary", "secondary"):
        raise ValueError("region must be 'primary' or 'secondary'")
    state["simulated_outage"][region_key] = down
    save_state(path, state)
    return state

