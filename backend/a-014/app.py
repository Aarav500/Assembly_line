import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import traceback
from datetime import datetime
from flask import Flask, request, jsonify

from analyzer.scanner import Scanner

app = Flask(__name__)


def json_response(obj, status=200):
    return app.response_class(
        response=json.dumps(obj, ensure_ascii=False),
        status=status,
        mimetype="application/json",
    )


@app.get("/health")
def health():
    return json_response({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})


@app.get("/rules")
def rules():
    scanner = Scanner()
    rules_meta = []
    for rule in scanner.list_rules():
        rules_meta.append({
            "rule_id": rule.rule_id,
            "name": rule.name,
            "category": rule.category,
            "default_severity": rule.default_severity,
            "description": rule.description,
            "scope": rule.scope,
        })
    return json_response({"rules": rules_meta})


@app.post("/scan")
def scan():
    try:
        payload = request.get_json(silent=True) or {}
        path = payload.get("path") or os.getcwd()
        include_categories = payload.get("include_categories")  # ["bugs","security","performance","tests"]
        exclude_globs = payload.get("exclude_globs")  # e.g., ["**/.venv/**", "**/migrations/**"]
        severity_threshold = payload.get("severity_threshold")  # one of low,medium,high,critical -> filter lower severities

        if not os.path.exists(path):
            return json_response({"error": f"Path not found: {path}"}, status=400)

        scanner = Scanner(include_categories=include_categories, exclude_globs=exclude_globs, severity_threshold=severity_threshold)
        result = scanner.scan(path)
        return json_response(result)
    except Exception as e:
        return json_response({
            "error": str(e),
            "trace": traceback.format_exc(),
        }, status=500)


if __name__ == "__main__":
    # Bind to 0.0.0.0 so it works in containers; do not enable debug by default
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)



def create_app():
    return app
