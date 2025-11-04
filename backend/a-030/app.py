import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import logging
from flask import Flask, request, jsonify

from config import Config
from services.issue_service import IssueCreationService
from storage.issue_registry import IssueRegistry

app = Flask(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

cfg = Config.from_env()
issue_registry = IssueRegistry(cfg.issue_registry_path)
issue_service = IssueCreationService(cfg, issue_registry)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "provider": cfg.tracker_provider}), 200


@app.route("/config", methods=["GET"]) 
def get_config():
    # Intentionally returns non-sensitive subset of config
    return jsonify({
        "tracker_provider": cfg.tracker_provider,
        "auto_create_issues": cfg.auto_create_issues,
    }), 200


@app.route("/gaps/report", methods=["POST"]) 
def report_gaps():
    if not request.is_json:
        return jsonify({"error": "Expected JSON payload"}), 400

    payload = request.get_json(silent=True) or {}
    gaps = payload.get("gaps", [])
    auto = payload.get("auto_create", cfg.auto_create_issues)

    if not isinstance(gaps, list) or not gaps:
        return jsonify({"error": "gaps must be a non-empty list"}), 400

    results = []
    for gap in gaps:
        try:
            if not isinstance(gap, dict):
                raise ValueError("Each gap must be an object")

            gap_id = str(gap.get("id") or gap.get("external_id") or "")
            if not gap_id:
                raise ValueError("gap.id (or external_id) is required")

            if not auto:
                results.append({
                    "gap_id": gap_id,
                    "status": "skipped",
                    "reason": "auto_create disabled",
                })
                continue

            created = issue_service.create_issue_for_gap(gap)
            results.append({
                "gap_id": gap_id,
                "status": "created" if created.get("created") else "exists",
                "issue_url": created.get("issue_url"),
                "issue_id": created.get("issue_id"),
                "provider": cfg.tracker_provider,
            })
        except Exception as e:
            logger.exception("Failed to process gap")
            results.append({
                "gap_id": gap.get("id") if isinstance(gap, dict) else None,
                "status": "error",
                "error": str(e),
            })

    return jsonify({"results": results}), 207


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))



def create_app():
    return app
