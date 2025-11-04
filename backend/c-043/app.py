import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, Response
from descriptors.generators import (
    generate_appengine_yaml,
    generate_serverless_yaml,
    normalize_appengine_config,
    normalize_serverless_config,
)

app = Flask(__name__)


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    return jsonify({
        "name": "auto-generated-deployment-descriptors-for-cloud-providers-ap",
        "stack": ["python", "flask"],
        "endpoints": {
            "appengine": {"method": "POST", "path": "/generate/appengine"},
            "serverless": {"method": "POST", "path": "/generate/serverless"},
            "generic": {"method": "POST", "path": "/generate"}
        },
        "samples": {
            "appengine": "sample_configs/appengine.json",
            "serverless": "sample_configs/serverless.json"
        }
    })


@app.post("/generate/appengine")
def generate_appengine():
    payload = request.get_json(force=True, silent=True) or {}
    cfg = normalize_appengine_config(payload)
    yaml_str = generate_appengine_yaml(cfg)
    return Response(yaml_str, mimetype="application/x-yaml")


@app.post("/generate/serverless")
def generate_serverless():
    payload = request.get_json(force=True, silent=True) or {}
    cfg = normalize_serverless_config(payload)
    yaml_str = generate_serverless_yaml(cfg)
    return Response(yaml_str, mimetype="application/x-yaml")


@app.post("/generate")
def generate_generic():
    data = request.get_json(force=True, silent=True) or {}
    kind = (data.get("kind") or "").lower()
    cfg = data.get("config") or {}

    if kind == "appengine":
        cfg = normalize_appengine_config(cfg)
        yaml_str = generate_appengine_yaml(cfg)
    elif kind == "serverless":
        cfg = normalize_serverless_config(cfg)
        yaml_str = generate_serverless_yaml(cfg)
    else:
        return jsonify({"error": "kind must be 'appengine' or 'serverless'"}), 400

    return Response(yaml_str, mimetype="application/x-yaml")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)



def create_app():
    return app


@app.route('/api/info', methods=['GET'])
def _auto_stub_api_info():
    return 'Auto-generated stub for /api/info', 200
