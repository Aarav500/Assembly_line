import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
from flask import Flask, jsonify, request, render_template
from werkzeug.exceptions import BadRequest

from config import ALLOWED_ROOT
from optimization.analyzer import ProjectAnalyzer
from optimization.passes.lazy_load_media import LazyLoadMediaPass
from optimization.passes.defer_scripts import DeferScriptsPass

app = Flask(__name__)


PASS_REGISTRY = {
    "lazy_load_media": {
        "class": LazyLoadMediaPass,
        "name": "Lazy-load media",
        "description": "Adds loading=\"lazy\" to <img> and <iframe> without it in HTML/Jinja templates.",
        "apply": True,
    },
    "defer_scripts": {
        "class": DeferScriptsPass,
        "name": "Defer blocking scripts",
        "description": "Adds defer to external <script> tags without async/defer to reduce render-blocking.",
        "apply": True,
    },
}


def resolve_and_validate_path(path_str: str) -> str:
    if not path_str:
        raise BadRequest("Missing 'path' parameter")
    abs_path = os.path.abspath(path_str)
    allowed = os.path.abspath(ALLOWED_ROOT)
    if not abs_path.startswith(allowed):
        raise BadRequest(f"Path '{abs_path}' is outside allowed root '{allowed}'")
    if not os.path.exists(abs_path):
        raise BadRequest(f"Path '{abs_path}' does not exist")
    return abs_path


@app.route("/")
def index():
    return render_template("index.html", allowed_root=os.path.abspath(ALLOWED_ROOT))


@app.route("/api/passes", methods=["GET"]) 
def list_passes():
    items = []
    for pid, meta in PASS_REGISTRY.items():
        items.append({
            "id": pid,
            "name": meta["name"],
            "description": meta["description"],
            "apply": meta["apply"],
        })
    return jsonify({"passes": items})


@app.route("/api/analyze", methods=["GET"]) 
def analyze():
    path = request.args.get("path", default=ALLOWED_ROOT)
    abs_path = resolve_and_validate_path(path)

    analyzer = ProjectAnalyzer()
    result = analyzer.analyze(abs_path)

    # Attach pass availability
    result["available_passes"] = [
        {"id": k, "name": v["name"], "description": v["description"], "apply": v["apply"]}
        for k, v in PASS_REGISTRY.items()
    ]
    return jsonify(result)


@app.route("/api/apply-pass", methods=["POST"]) 
def apply_pass():
    try:
        payload = request.get_json(force=True)
    except Exception:
        raise BadRequest("Invalid JSON body")
    pass_id = payload.get("pass")
    path = payload.get("path", ALLOWED_ROOT)
    dry_run = bool(payload.get("dry_run", False))

    if pass_id not in PASS_REGISTRY:
        raise BadRequest(f"Unknown pass '{pass_id}'")

    abs_path = resolve_and_validate_path(path)

    pass_cls = PASS_REGISTRY[pass_id]["class"]
    pass_instance = pass_cls()

    report = pass_instance.apply(abs_path, dry_run=dry_run)

    return jsonify({
        "pass": pass_id,
        "dry_run": dry_run,
        "report": report,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



def create_app():
    return app


@app.route('/suggest', methods=['GET'])
def _auto_stub_suggest():
    return 'Auto-generated stub for /suggest', 200


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
