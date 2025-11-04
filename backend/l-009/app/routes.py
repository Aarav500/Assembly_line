import os
from flask import Blueprint, jsonify, current_app, request
from datetime import datetime

api_bp = Blueprint("api", __name__)


def services():
    return current_app.extensions["services"]


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})


@api_bp.get("/backups")
def list_backups():
    items = services().storage.list_backups()
    # Sort by timestamp desc
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(items)


@api_bp.get("/backups/<backup_id>")
def get_backup(backup_id):
    meta = services().storage.get_metadata(backup_id)
    if not meta:
        return jsonify({"error": "not_found"}), 404
    return jsonify(meta)


@api_bp.delete("/backups/<backup_id>")
def delete_backup(backup_id):
    try:
        services().storage.delete_backup(backup_id)
        return jsonify({"deleted": backup_id})
    except FileNotFoundError:
        return jsonify({"error": "not_found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/backup")
def create_backup():
    payload = request.get_json(silent=True) or {}
    sources = payload.get("sources")
    reason = payload.get("reason", "api")
    try:
        result = services().backup.create_backup(reason=reason, sources=sources)
        status = 200 if result.get("status") == "success" else 500
        return jsonify(result), status
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 500


@api_bp.post("/restore")
def restore():
    payload = request.get_json() or {}
    backup_id = payload.get("backup_id")
    target_path = payload.get("target_path")
    verify_checksum = bool(payload.get("verify_checksum", True))
    if not backup_id or not target_path:
        return jsonify({"error": "backup_id and target_path required"}), 400
    try:
        result = services().restore.restore_backup(backup_id=backup_id, target_path=target_path, verify_checksum=verify_checksum)
        return jsonify(result)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/retention/run")
def run_retention():
    try:
        result = services().retention.apply()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/drill")
def run_drill():
    payload = request.get_json(silent=True) or {}
    backup_id = payload.get("backup_id")
    try:
        result = services().scheduler.run_drill_now(backup_id=backup_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.get("/drill/results")
def drill_results():
    base = services().storage.base_path
    drill_dir = os.path.join(base, "drills")
    results = []
    if os.path.isdir(drill_dir):
        for name in os.listdir(drill_dir):
            if name.endswith(".json"):
                try:
                    with open(os.path.join(drill_dir, name), "r", encoding="utf-8") as f:
                        import json
                        results.append(json.load(f))
                except Exception:
                    continue
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(results)

