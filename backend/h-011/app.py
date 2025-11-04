import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import time
import json
from datetime import datetime
from flask import Flask, request, jsonify
from storage import Storage
from drift_detection import build_baseline_from_data, compute_drift_for_batch, infer_feature_types
from alerting import AlertManager

app = Flask(__name__)
storage = Storage(os.environ.get("DRIFT_DATA_DIR", "data"))
alerts = AlertManager()


def iso_now():
    return datetime.utcnow().isoformat() + "Z"


@app.route("/status", methods=["GET"])
def status():
    cfg = storage.load_config()
    baseline = storage.get_baseline()
    history = storage.get_history(limit=1)
    return jsonify({
        "ok": True,
        "baseline_available": baseline is not None,
        "last_batch": history[0] if history else None,
        "config": {
            "thresholds": cfg.get("thresholds", {}),
            "alerts": {k: ("***" if v else None) if k.endswith("_secret") else v for k, v in cfg.get("alerts", {}).items()}
        }
    })


@app.route("/config", methods=["GET"]) 
def get_config():
    cfg = storage.load_config()
    return jsonify(cfg)


@app.route("/config", methods=["POST"]) 
def update_config():
    payload = request.get_json(force=True, silent=True) or {}
    cfg = storage.load_config()
    # Shallow merge for simplicity
    for k, v in payload.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    storage.save_config(cfg)
    return jsonify({"ok": True, "config": cfg})


@app.route("/baseline", methods=["POST"]) 
def set_baseline():
    payload = request.get_json(force=True, silent=True) or {}
    data = payload.get("data")
    feature_types = payload.get("feature_types")
    bins = payload.get("bins")  # optional per-feature dict or int

    if not isinstance(data, list) or len(data) == 0:
        return jsonify({"ok": False, "error": "data must be a non-empty list of records"}), 400

    if feature_types is None:
        feature_types = infer_feature_types(data)

    baseline = build_baseline_from_data(data, feature_types=feature_types, bins=bins)
    storage.save_baseline(baseline)

    return jsonify({
        "ok": True,
        "baseline": {
            "created_at": baseline.get("created_at"),
            "feature_types": baseline.get("feature_types"),
            "features": {k: {"type": v.get("type"), "summary": v.get("baseline", {}).get("summary")} for k, v in baseline.get("features", {}).items()}
        }
    })


@app.route("/ingest", methods=["POST"]) 
def ingest():
    payload = request.get_json(force=True, silent=True) or {}
    data = payload.get("data")
    batch_id = payload.get("batch_id") or str(uuid.uuid4())
    meta = payload.get("meta", {})

    if not isinstance(data, list) or len(data) == 0:
        return jsonify({"ok": False, "error": "data must be a non-empty list of records"}), 400

    baseline = storage.get_baseline()
    if baseline is None:
        return jsonify({"ok": False, "error": "baseline not set. POST /baseline first."}), 400

    cfg = storage.load_config()

    metrics_by_feature, drifted_features, overall_drift = compute_drift_for_batch(
        baseline, data, cfg.get("thresholds", {})
    )

    entry = {
        "batch_id": batch_id,
        "timestamp": iso_now(),
        "size": len(data),
        "meta": meta,
        "metrics_by_feature": metrics_by_feature,
        "drifted_features": drifted_features,
        "overall_drift": overall_drift
    }

    storage.append_history(entry)

    # Auto-alerts
    if overall_drift and drifted_features:
        try:
            alerts.send_drift_alert(cfg.get("alerts", {}), entry)
        except Exception as e:
            # Log but don't fail request
            print(f"[alerts] failed to send alert: {e}")

    return jsonify({"ok": True, **entry})


@app.route("/metrics", methods=["GET"]) 
def metrics():
    try:
        limit = int(request.args.get("limit", "50"))
    except Exception:
        limit = 50
    history = storage.get_history(limit=limit)
    return jsonify({"ok": True, "items": history})


@app.route("/events", methods=["GET"]) 
def events():
    try:
        limit = int(request.args.get("limit", "100"))
    except Exception:
        limit = 100
    events = storage.get_events(limit=limit)
    return jsonify({"ok": True, "items": events})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/reference', methods=['POST'])
def _auto_stub_reference():
    return 'Auto-generated stub for /reference', 200


@app.route('/monitor', methods=['POST'])
def _auto_stub_monitor():
    return 'Auto-generated stub for /monitor', 200


@app.route('/alerts', methods=['GET'])
def _auto_stub_alerts():
    return 'Auto-generated stub for /alerts', 200
