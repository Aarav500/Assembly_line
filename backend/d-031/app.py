import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, request
from compliance.runner import run_checks
from compliance.config import load_config

app = Flask(__name__)


def _response(only=None, fail_on=None, config_override=None):
    config = load_config(override=config_override)
    report = run_checks(config=config, only=only, fail_on=fail_on)
    return jsonify(report)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/checks")
def checks_all():
    only = request.args.get("only")
    fail_on = request.args.get("fail_on")
    return _response(only=only, fail_on=fail_on)


@app.get("/api/checks/gdpr")
def checks_gdpr():
    return _response(only="gdpr")


@app.get("/api/checks/hipaa")
def checks_hipaa():
    return _response(only="hipaa")


@app.post("/api/run")
def run_endpoint():
    data = request.get_json(silent=True) or {}
    only = data.get("only")
    fail_on = data.get("fail_on")
    config_override = data.get("config")
    return _response(only=only, fail_on=fail_on, config_override=config_override)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/compliance/gdpr', methods=['GET'])
def _auto_stub_compliance_gdpr():
    return 'Auto-generated stub for /compliance/gdpr', 200


@app.route('/compliance/gdpr/check', methods=['POST'])
def _auto_stub_compliance_gdpr_check():
    return 'Auto-generated stub for /compliance/gdpr/check', 200
