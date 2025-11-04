from flask import Blueprint, jsonify, request, current_app, render_template, abort
from typing import Any, Dict

bp = Blueprint("flags", __name__, url_prefix="/_flags")


def _store():
    return current_app.extensions["feature_flags"]


@bp.get("/")
def list_flags():
    items = []
    for name, rec in _store().all().items():
        out = {"name": name}
        out.update(rec)
        items.append(out)
    items.sort(key=lambda x: x["name"])  # deterministic order
    return jsonify({"flags": items})


@bp.get("/<name>")
def get_flag(name: str):
    rec = _store().get_record(name)
    if rec is None:
        abort(404)
    out = {"name": name}
    out.update(rec)
    return jsonify(out)


@bp.put("/<name>")
def put_flag(name: str):
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    if "enabled" not in data:
        return jsonify({"error": "'enabled' is required"}), 400
    enabled = bool(data.get("enabled"))
    description = data.get("description")
    expires_on = data.get("expires_on")
    rec = _store().set(name=name, enabled=enabled, description=description, expires_on=expires_on)
    out = {"name": name}
    out.update(rec)
    return jsonify(out)


@bp.post("/bulk")
def bulk_update():
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list):
        return jsonify({"error": "'items' must be a list"}), 400
    results = []
    for item in items:
        if not isinstance(item, dict) or "name" not in item or "enabled" not in item:
            return jsonify({"error": "each item must include 'name' and 'enabled'"}), 400
        name = item["name"]
        enabled = bool(item["enabled"])
        description = item.get("description")
        expires_on = item.get("expires_on")
        rec = _store().set(name=name, enabled=enabled, description=description, expires_on=expires_on)
        out = {"name": name}
        out.update(rec)
        results.append(out)
    return jsonify({"updated": results})


@bp.get("/ui")
def flags_ui():
    # Simple HTML UI to view and toggle flags
    flags = []
    for name, rec in _store().all().items():
        item = {"name": name}
        item.update(rec)
        flags.append(item)
    flags.sort(key=lambda x: x["name"])  # deterministic order
    return render_template("flags_ui.html", flags=flags)

