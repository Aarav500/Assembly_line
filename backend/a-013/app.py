import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
import time
from datetime import datetime, timezone
from flask import Flask, request, jsonify

from analyzer.upgrade import suggest_upgrade_paths
from analyzer.requirements_parser import parse_requirements_text, parse_dependencies_json

app = Flask(__name__)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@app.get("/")
def root():
    return jsonify({
        "name": "suggest-upgrade-paths-for-dependencies-and-frameworks-compat",
        "status": "ok",
        "time": _now_iso(),
        "endpoints": ["POST /api/upgrade-paths"],
    })


@app.post("/api/upgrade-paths")
def api_upgrade_paths():
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    requirements_text = payload.get("requirements_text")
    dependencies = payload.get("dependencies")  # list of {name, spec} optional
    target_python = (payload.get("target_python") or str(os.environ.get("TARGET_PYTHON", "")).strip()) or None
    target_frameworks = payload.get("target_frameworks") or {}
    include_prereleases = bool(payload.get("include_prereleases", False))

    if not requirements_text and not dependencies:
        return jsonify({"error": "Provide either requirements_text or dependencies list"}), 400

    parse_errors = []
    parsed = []
    if requirements_text:
        parsed, errs = parse_requirements_text(requirements_text)
        parse_errors.extend(errs)
    if dependencies:
        parsed2, errs2 = parse_dependencies_json(dependencies)
        parse_errors.extend(errs2)
        parsed.extend(parsed2)

    # Deduplicate by canonical name, prefer pinned specs over ranges when duplicates occur
    dedup = {}
    for item in parsed:
        key = item["name_normalized"]
        prev = dedup.get(key)
        if not prev:
            dedup[key] = item
        else:
            # prefer the one with a pinned_version; else keep the first
            if item.get("pinned_version") and not prev.get("pinned_version"):
                dedup[key] = item

    parsed_unique = list(dedup.values())

    results = suggest_upgrade_paths(
        parsed_unique,
        target_python=target_python,
        target_frameworks=target_frameworks,
        include_prereleases=include_prereleases,
    )

    response = {
        "analyzed_at": _now_iso(),
        "target_python": target_python,
        "target_frameworks": target_frameworks,
        "parse_errors": parse_errors,
        "summary": results.get("summary", {}),
        "suggestions": results.get("suggestions", []),
        "errors": results.get("errors", []),
    }
    return app.response_class(
        response=json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        status=200,
        mimetype="application/json",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))



def create_app():
    return app


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}