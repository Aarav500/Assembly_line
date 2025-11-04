from flask import Blueprint, current_app, jsonify, request

from .db import Database
from .fleet import FleetManager

bp = Blueprint("api", __name__)


def _fm() -> FleetManager:
    # Initialize a FleetManager per request using current_app config and shared Database
    db = Database(current_app.config["DATABASE_PATH"])  # shares same file; sqlite is fine with multi-connections
    return FleetManager(db=db, config=current_app.config)


@bp.get("/settings")
def get_settings():
    fm = _fm()
    return jsonify(fm.settings())


@bp.post("/settings")
def update_settings():
    fm = _fm()
    data = request.get_json(silent=True) or {}
    fm.set_settings(
        min_capacity=data.get("min_capacity"),
        max_capacity=data.get("max_capacity"),
        desired_capacity=data.get("desired_capacity"),
        scale_down_idle_minutes=data.get("scale_down_idle_minutes"),
        labels=data.get("labels"),
        name_prefix=data.get("name_prefix"),
    )
    return jsonify({"ok": True, "settings": fm.settings()})


@bp.get("/runners")
def list_runners():
    fm = _fm()
    return jsonify(fm.inventory())


@bp.post("/provision")
def provision():
    if not current_app.config["ALLOW_MANUAL_PROVISION"]:
        return jsonify({"error": "manual provision disabled"}), 403
    fm = _fm()
    data = request.get_json(silent=True) or {}
    count = int(data.get("count", 1))
    created = []
    for _ in range(max(1, count)):
        created.append(fm.provision_one())
    return jsonify({"created": created})


@bp.post("/terminate")
def terminate():
    fm = _fm()
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    ok = fm.terminate_runner(name)
    return jsonify({"terminated": ok})


@bp.post("/reconcile")
def reconcile():
    fm = _fm()
    result = fm.reconcile()
    return jsonify(result)

