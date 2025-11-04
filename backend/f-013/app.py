import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, request
from orchestrator import Orchestrator
from utils import load_config, get_admin_token


config = load_config()
orchestrator = Orchestrator()
orchestrator.start()

app = Flask(__name__)


def _auth_ok() -> bool:
    token = get_admin_token(config)
    if not token:
        return True
    provided = request.headers.get("X-Admin-Token") or request.args.get("token")
    return provided == token


@app.get("/health/live")
def live():
    return jsonify({"status": "ok"})


@app.get("/health/ready")
def ready():
    return jsonify(orchestrator.overall_ready())


@app.get("/health/details")
def details():
    return jsonify({"status": "ok", "checks": orchestrator.snapshot()})


@app.post("/heal/<check_name>")
def heal(check_name: str):
    if not _auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    params = data.get("params")
    res = orchestrator.manual_heal(check_name, action=action, params=params)
    if "error" in res:
        return jsonify(res), 400
    return jsonify(res)


@app.post("/run-check/<check_name>")
def run_check_endpoint(check_name: str):
    if not _auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    res = orchestrator.manual_run_check(check_name)
    return jsonify(res)


@app.get("/incidents")
def incidents():
    if not _auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"incidents": orchestrator.incidents})


if __name__ == "__main__":
    host = (config.get("app", {}) or {}).get("host", "0.0.0.0")
    port = int((config.get("app", {}) or {}).get("port", 8080))
    app.run(host=host, port=port)



def create_app():
    return app


@app.route('/status', methods=['GET'])
def _auto_stub_status():
    return 'Auto-generated stub for /status', 200
