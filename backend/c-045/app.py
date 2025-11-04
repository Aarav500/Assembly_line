import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from hygiene.runner import run_passes

app = Flask(__name__)

# Optionally restrict scanning to a base directory for safety
BASE_DIR = os.environ.get("HYGIENE_BASE_DIR")


def is_path_allowed(path: str) -> bool:
    if not BASE_DIR:
        return True
    try:
        real_base = os.path.realpath(BASE_DIR)
        real_path = os.path.realpath(path)
        return os.path.commonpath([real_base]) == os.path.commonpath([real_base, real_path])
    except Exception:
        return False


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/run")
def run():
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    target_path = data.get("path", ".")
    passes = data.get("passes", ["duplicate", "dead_code"])  # default run both
    options = data.get("options", {})

    if not isinstance(passes, list) or not all(isinstance(p, str) for p in passes):
        return jsonify({"error": "'passes' must be a list of strings"}), 400

    if not os.path.exists(target_path):
        return jsonify({"error": f"Path not found: {target_path}"}), 400

    if not is_path_allowed(target_path):
        return jsonify({"error": "Path is outside allowed base directory"}), 403

    try:
        results = run_passes(target_path, passes=passes, options=options)
        return app.response_class(
            response=json.dumps(results, ensure_ascii=False, indent=2),
            status=200,
            mimetype="application/json",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/analyze/duplicates', methods=['POST'])
def _auto_stub_analyze_duplicates():
    return 'Auto-generated stub for /analyze/duplicates', 200


@app.route('/analyze/dead-code', methods=['POST'])
def _auto_stub_analyze_dead_code():
    return 'Auto-generated stub for /analyze/dead-code', 200
