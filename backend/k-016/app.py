import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from services.policy_engine import PolicyEngine, PolicyNotFound, ValidationError
from services.behaviors import decide_trade

app = Flask(__name__)
engine = PolicyEngine(os.getenv("POLICIES_FILE", "config/policies.json"))


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/policies")
def list_policies():
    data = engine.list_policies()
    return jsonify({"policies": list(data.keys()), "count": len(data)})


@app.get("/policies/<name>")
def get_policy(name: str):
    try:
        policy = engine.get_policy(name)
        return jsonify({"name": name, "params": policy})
    except PolicyNotFound:
        return jsonify({"error": f"policy '{name}' not found"}), 404


@app.post("/policies")
def set_policy():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name") or payload.get("policy") or payload.get("id")
    params = payload.get("params") or payload.get("data") or {}

    if isinstance(name, dict) and not params:
        # Allow { "policy": {"name": ..., "params": {...}} }
        pol = name
        name = pol.get("name")
        params = pol.get("params") or {}

    if not name or not isinstance(params, dict):
        return jsonify({"error": "invalid payload. expected: { 'name': str, 'params': { ... } }"}), 400

    try:
        engine.set_policy(name, params)
        return jsonify({"message": "policy upserted", "name": name, "params": engine.get_policy(name)})
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400


@app.delete("/policies/<name>")
def delete_policy(name: str):
    try:
        engine.delete_policy(name)
        return jsonify({"message": "policy deleted", "name": name})
    except PolicyNotFound:
        return jsonify({"error": f"policy '{name}' not found"}), 404


@app.post("/decide")
def decide():
    body = request.get_json(silent=True) or {}
    policy_name = body.get("policy") or body.get("profile") or "conservative"
    task = (body.get("task") or "trade").lower()
    state = body.get("state") or {}

    try:
        policy = engine.get_policy(policy_name)
    except PolicyNotFound:
        return jsonify({"error": f"policy '{policy_name}' not found"}), 404

    if task == "trade":
        try:
            decision = decide_trade(state, policy)
        except Exception as e:
            return jsonify({"error": f"failed to decide: {e}"}), 400
        return jsonify({
            "task": task,
            "policy": policy_name,
            "decision": decision
        })
    else:
        return jsonify({"error": f"unsupported task '{task}'"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)



def create_app():
    return app


@app.route('/agent', methods=['POST'])
def _auto_stub_agent():
    return 'Auto-generated stub for /agent', 200


@app.route('/agent/agent3/decide', methods=['POST'])
def _auto_stub_agent_agent3_decide():
    return 'Auto-generated stub for /agent/agent3/decide', 200


@app.route('/agent/agent4/decide', methods=['POST'])
def _auto_stub_agent_agent4_decide():
    return 'Auto-generated stub for /agent/agent4/decide', 200
