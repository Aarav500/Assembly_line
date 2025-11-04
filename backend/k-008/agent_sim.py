from __future__ import annotations

import threading
from typing import Dict, Tuple
from flask import Blueprint, jsonify, request

agents_blueprint = Blueprint("agents", __name__)

# Simple in-memory state for simulation: counters per (agent_name, session_id)
_STATE_LOCK = threading.Lock()
_ATTEMPTS: Dict[Tuple[str, str], int] = {}
_THRESHOLDS: Dict[Tuple[str, str], int] = {}


def _get_session_id(payload: dict) -> str:
    simulate = payload.get("simulate", {}) if isinstance(payload, dict) else {}
    return str(simulate.get("session", "default"))


def _get_threshold_for(agent: str, session: str, payload: dict) -> int:
    simulate = payload.get("simulate", {}) if isinstance(payload, dict) else {}
    per_agent = simulate.get("failures_before_success", {}) if isinstance(simulate.get("failures_before_success", {}), dict) else {}

    # First, check per-agent override
    if isinstance(per_agent, dict) and agent in per_agent:
        return int(per_agent.get(agent, 0))

    # Then, global threshold for all agents
    global_threshold = simulate.get("failures_before_success")
    if isinstance(global_threshold, int):
        return global_threshold

    return 0


@agents_blueprint.post("/agent/<string:agent>/process")
def process(agent: str):
    payload = request.get_json(silent=True) or {}
    session_id = _get_session_id(payload)
    key = (agent, session_id)

    force_status = None
    simulate = payload.get("simulate", {}) if isinstance(payload, dict) else {}
    if isinstance(simulate, dict):
        force_status = simulate.get("force_status")

    delay_ms = 0
    if isinstance(simulate, dict):
        delay_ms = int(simulate.get("delay_ms", 0) or 0)

    if delay_ms > 0:
        import time
        time.sleep(min(delay_ms / 1000.0, 5))

    # If forced status is provided, honor it directly
    if force_status is not None:
        try:
            status = int(force_status)
        except Exception:
            status = 500
        return jsonify({
            "agent": agent,
            "session": session_id,
            "forced_status": status,
        }), status

    with _STATE_LOCK:
        current = _ATTEMPTS.get(key, 0) + 1
        _ATTEMPTS[key] = current
        # Load or set thresholds lazily
        if key not in __THRESHOLDS:
            __THRESHOLDS[key] = _get_threshold_for(agent, session_id, payload)
        threshold = __THRESHOLDS[key]

    if current <= threshold:
        # Simulate transient error
        return jsonify({
            "agent": agent,
            "session": session_id,
            "attempt": current,
            "threshold": threshold,
            "status": "transient_failure",
        }), 503

    # Success
    return jsonify({
        "agent": agent,
        "session": session_id,
        "attempt": current,
        "threshold": threshold,
        "status": "ok",
        "echo": payload.get("data"),
    })

