import os
import time
from flask import Blueprint, jsonify, request, abort

routes_bp = Blueprint("routes", __name__)


def is_sandbox() -> bool:
    return os.getenv("SANDBOX_MODE", "0").lower() in {"1", "true", "yes"}


@routes_bp.get("/health")
def health():
    # A minimal health endpoint used by smoke tests to verify the app is up
    return jsonify(
        {
            "status": "ok",
            "service": "pre-merge-sandbox",
            "env": "sandbox" if is_sandbox() else "live",
            "ts": int(time.time()),
        }
    )


@routes_bp.post("/echo")
def echo():
    # Simple echo endpoint for smoke testing request/response roundtrip
    data = request.get_json(silent=True) or {}
    meta = {
        "method": request.method,
        "path": request.path,
        "sandbox": is_sandbox(),
        "content_type": request.content_type,
    }
    return jsonify({"data": data, "meta": meta}), 200


@routes_bp.post("/critical-action")
def critical_action():
    # Represents a sensitive route. In sandbox this is disabled to be safe.
    if is_sandbox():
        abort(403, description="Critical action is disabled in sandbox mode")
    payload = request.get_json(silent=True) or {}
    # In a real app, some sensitive side-effect would occur here.
    return jsonify({"result": "critical action executed", "received": payload}), 200

