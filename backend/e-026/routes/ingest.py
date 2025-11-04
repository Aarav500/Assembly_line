from flask import Blueprint, request, current_app
from utils.json_store import upsert_resources, load_ingested_resources, save_config

ingest_bp = Blueprint("ingest", __name__)


@ingest_bp.post("/ingest/metrics")
def ingest_metrics():
    payload = request.get_json(silent=True) or {}
    resources = payload.get("resources", [])
    if not isinstance(resources, list) or not resources:
        return {"error": "Provide resources as a non-empty list"}, 400

    file_path = current_app.config["INGESTED_FILE"]
    upsert_resources(file_path, resources)
    stored = load_ingested_resources(file_path)
    return {"status": "ok", "ingested_count": len(resources), "total": len(stored)}


@ingest_bp.post("/config")
def update_config():
    cfg_payload = request.get_json(silent=True) or {}
    if not isinstance(cfg_payload, dict):
        return {"error": "Invalid config payload"}, 400

    # Only allow known keys
    allowed = {"savings_alert_threshold", "high_savings_threshold", "idle_hours_threshold"}
    updates = {k: v for k, v in cfg_payload.items() if k in allowed}
    if not updates:
        return {"error": "No valid config keys provided"}, 400

    cfg_file = current_app.config["CONFIG_FILE"]
    save_config(cfg_file, updates)

    # Reflect in runtime config
    if "savings_alert_threshold" in updates:
        current_app.config["SAVINGS_ALERT_THRESHOLD"] = float(updates["savings_alert_threshold"])
    if "high_savings_threshold" in updates:
        current_app.config["HIGH_SAVINGS_THRESHOLD"] = float(updates["high_savings_threshold"])
    if "idle_hours_threshold" in updates:
        current_app.config["IDLE_HOURS_THRESHOLD"] = int(updates["idle_hours_threshold"])

    effective = {
        "savings_alert_threshold": current_app.config["SAVINGS_ALERT_THRESHOLD"],
        "high_savings_threshold": current_app.config["HIGH_SAVINGS_THRESHOLD"],
        "idle_hours_threshold": current_app.config["IDLE_HOURS_THRESHOLD"],
    }
    return {"status": "ok", "config": effective}

