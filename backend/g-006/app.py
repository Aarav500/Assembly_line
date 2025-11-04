import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_file, abort

from generator.model_card import generate_model_card
from generator.compliance import generate_compliance
from storage.repo import FileRepo
from utils.common import slugify


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_model_record(payload, model_id=None):
    name = (payload.get("name") or "unnamed-model").strip()
    version = (payload.get("version") or "0.0.1").strip()
    if not model_id:
        base = f"{name}-{version}"
        model_id = f"{slugify(base)}-{str(uuid.uuid4())[:8]}"

    record = {
        "id": model_id,
        "name": name,
        "version": version,
        "owner": payload.get("owner", {}),
        "description": payload.get("description", ""),
        "intended_use": payload.get("intended_use", {}),
        "model_details": payload.get("model_details", {}),
        "training_data": payload.get("training_data", {}),
        "evaluation": payload.get("evaluation", {}),
        "risk_management": payload.get("risk_management", {}),
        "deployment": payload.get("deployment", {}),
        "compliance": payload.get("compliance", {}),
        "tags": payload.get("tags", []),
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    return record


def validate_payload(payload):
    errors = []
    if not isinstance(payload, dict):
        return ["Payload must be a JSON object."]
    if not payload.get("name"):
        errors.append("'name' is required.")
    if not payload.get("version"):
        errors.append("'version' is required.")
    if payload.get("owner") and not isinstance(payload["owner"], dict):
        errors.append("'owner' must be an object.")
    return errors


def create_app():
    app = Flask(__name__)
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
    repo = FileRepo(base_dir=data_dir)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/models", methods=["GET"])
    def list_models():
        items = repo.list_models()
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/models", methods=["POST"])
    def create_model():
        try:
            payload = request.get_json(force=True, silent=False)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400

        errs = validate_payload(payload)
        if errs:
            return jsonify({"errors": errs}), 400

        record = build_model_record(payload)
        compliance = generate_compliance(record)
        card_md = generate_model_card(record, compliance)

        artifact_paths = repo.save_model_record(record, {
            "model.json": json.dumps(record, indent=2, ensure_ascii=False),
            "model_card.md": card_md,
            "compliance.json": json.dumps(compliance, indent=2, ensure_ascii=False)
        })

        response = {
            **record,
            "artifacts": artifact_paths,
            "links": {
                "self": f"/api/models/{record['id']}",
                "card": f"/api/models/{record['id']}/card",
                "compliance": f"/api/models/{record['id']}/compliance"
            }
        }
        return jsonify(response), 201

    @app.route("/api/models/<model_id>", methods=["GET"])
    def get_model(model_id):
        record = repo.load_model(model_id)
        if not record:
            return jsonify({"error": "Not found"}), 404
        # Include artifact paths
        artifacts = repo.get_artifact_paths(model_id)
        record_out = {
            **record,
            "artifacts": artifacts,
            "links": {
                "self": f"/api/models/{model_id}",
                "card": f"/api/models/{model_id}/card",
                "compliance": f"/api/models/{model_id}/compliance"
            }
        }
        return jsonify(record_out)

    @app.route("/api/models/<model_id>/card", methods=["GET"])
    def get_model_card(model_id):
        path = repo.get_file_path(model_id, "model_card.md")
        if not path or not os.path.exists(path):
            return jsonify({"error": "Model card not found"}), 404
        return send_file(path, mimetype="text/markdown")

    @app.route("/api/models/<model_id>/compliance", methods=["GET"])
    def get_model_compliance(model_id):
        path = repo.get_file_path(model_id, "compliance.json")
        if not path or not os.path.exists(path):
            return jsonify({"error": "Compliance metadata not found"}), 404
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)

    @app.route("/api/models/<model_id>/regenerate", methods=["POST"])
    def regenerate(model_id):
        record = repo.load_model(model_id)
        if not record:
            return jsonify({"error": "Not found"}), 404
        record["updated_at"] = utc_now_iso()
        compliance = generate_compliance(record)
        card_md = generate_model_card(record, compliance)
        repo.write_artifacts(model_id, {
            "model.json": json.dumps(record, indent=2, ensure_ascii=False),
            "model_card.md": card_md,
            "compliance.json": json.dumps(compliance, indent=2, ensure_ascii=False)
        })
        return jsonify({"status": "regenerated", "id": model_id})

    @app.route("/api/models/<model_id>", methods=["PATCH", "PUT"])
    def update_model(model_id):
        record = repo.load_model(model_id)
        if not record:
            return jsonify({"error": "Not found"}), 404
        try:
            payload = request.get_json(force=True, silent=False)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400
        # Merge top-level keys
        mutable_fields = [
            "name", "version", "owner", "description", "intended_use",
            "model_details", "training_data", "evaluation", "risk_management",
            "deployment", "compliance", "tags"
        ]
        for k in mutable_fields:
            if k in payload:
                record[k] = payload[k]
        record["updated_at"] = utc_now_iso()

        compliance = generate_compliance(record)
        card_md = generate_model_card(record, compliance)
        repo.write_artifacts(model_id, {
            "model.json": json.dumps(record, indent=2, ensure_ascii=False),
            "model_card.md": card_md,
            "compliance.json": json.dumps(compliance, indent=2, ensure_ascii=False)
        })
        return jsonify({"status": "updated", "id": model_id})

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



@app.route('/generate-model-card', methods=['POST'])
def _auto_stub_generate_model_card():
    return 'Auto-generated stub for /generate-model-card', 200


@app.route('/validate-compliance', methods=['POST'])
def _auto_stub_validate_compliance():
    return 'Auto-generated stub for /validate-compliance', 200
