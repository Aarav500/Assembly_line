import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from flask import Flask, request, jsonify
from planners.planner import plan_deployment
from exporters.terraform import generate_terraform_files
from utils.validation import validate_spec

app = Flask(__name__)


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/plan", methods=["POST"]) 
def plan():
    try:
        data = request.get_json(force=True)
        validate_spec(data)
        plan = plan_deployment(data)
        return jsonify(plan)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/export/iac", methods=["POST"]) 
def export_iac():
    try:
        data = request.get_json(force=True)
        target = data.get("target", "terraform")
        if target != "terraform":
            return jsonify({"error": "Only 'terraform' target is supported currently."}), 400

        plan = data.get("plan")
        if not plan:
            # If plan is not provided, compute from spec
            spec = data.get("spec")
            if not spec:
                return jsonify({"error": "Provide either 'plan' or 'spec' in request body."}), 400
            validate_spec(spec)
            plan = plan_deployment(spec)

        files = generate_terraform_files(plan)
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)



def create_app():
    return app


@app.route('/deployments', methods=['POST'])
def _auto_stub_deployments():
    return 'Auto-generated stub for /deployments', 200


@app.route('/deployments/deploy-002/export', methods=['GET'])
def _auto_stub_deployments_deploy_002_export():
    return 'Auto-generated stub for /deployments/deploy-002/export', 200
