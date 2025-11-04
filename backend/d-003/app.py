import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from __future__ import annotations
import json
import os
from flask import Flask, request, jsonify
from manifest_checker.checker import run_check

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/check")
def check():
    data = request.get_json(silent=True) or {}
    manifest_path = data.get("manifest_path") or os.environ.get("MANIFEST_PATH", "manifest.json")
    required_path = data.get("required_path") or os.environ.get("REQUIRED_FEATURES_PATH", "manifest_checker/required_features.yaml")
    features_key = data.get("features_key") or os.environ.get("MANIFEST_FEATURES_KEY", "features")
    base_ref = data.get("base_ref") or os.environ.get("BASE_REF") or os.environ.get("GIT_BASE_REF")

    result = run_check(
        manifest_path=manifest_path,
        required_path=required_path,
        features_key=features_key,
        base_ref=base_ref,
    )
    status = 200 if result.get("ok") else 422
    return jsonify(result), status


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/check-manifest', methods=['POST'])
def _auto_stub_check_manifest():
    return 'Auto-generated stub for /check-manifest', 200
