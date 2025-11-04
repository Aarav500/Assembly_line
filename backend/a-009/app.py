import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
from flask import Flask, request, jsonify
from gap_analyzer.ideater_manifest import load_manifest_from_dict, load_manifest_from_path
from gap_analyzer.detector import detect_from_repo_files, detect_from_repo_path
from gap_analyzer.analyzer import analyze_gaps


def create_app():
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/gap-analysis")
    def gap_analysis():
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400

        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object"}), 400

        # Load manifest
        manifest = None
        manifest_warnings = []
        if "manifest" in payload and isinstance(payload["manifest"], dict):
            manifest, manifest_warnings = load_manifest_from_dict(payload["manifest"])
        elif "manifest_path" in payload and isinstance(payload["manifest_path"], str):
            manifest_path = payload["manifest_path"]
            if not os.path.exists(manifest_path):
                return jsonify({"error": f"manifest_path not found: {manifest_path}"}), 400
            manifest, manifest_warnings = load_manifest_from_path(manifest_path)
        else:
            return jsonify({"error": "Provide 'manifest' (object) or 'manifest_path' (string)"}), 400

        # Detect repo state
        detection = None
        if "repo" in payload and isinstance(payload["repo"], dict) and isinstance(payload["repo"].get("files"), list):
            detection = detect_from_repo_files(payload["repo"]["files"], options=payload.get("options") or {})
        elif "repo_path" in payload and isinstance(payload["repo_path"], str):
            repo_path = payload["repo_path"]
            if not os.path.exists(repo_path):
                return jsonify({"error": f"repo_path not found: {repo_path}"}), 400
            detection = detect_from_repo_path(repo_path, options=payload.get("options") or {})
        else:
            return jsonify({"error": "Provide 'repo' with 'files' array or 'repo_path'"}), 400

        # Analyze
        analysis = analyze_gaps(manifest, detection)
        if manifest_warnings:
            analysis["warnings"] = manifest_warnings

        return jsonify(analysis)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

