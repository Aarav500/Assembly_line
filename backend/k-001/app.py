import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from orchestrator import Orchestrator

app = Flask(__name__)
orc = Orchestrator()

@app.route("/", methods=["GET"])  # Simple health check
def index():
    return jsonify({
        "service": "multi-agent-orchestration-with-role-assignment-planner-build",
        "stack": "python, flask",
        "roles": ["Planner", "Builder", "Tester", "Repair"]
    })

@app.route("/orchestrate", methods=["POST"])  # Orchestrate pipeline
def orchestrate():
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "Invalid or missing JSON"}), 400

    goal = payload.get("goal") or payload.get("task") or payload.get("description")
    user_tests = payload.get("tests")
    function_name = payload.get("function_name")
    max_iters = int(payload.get("max_iters", 3))

    if not goal and not (user_tests and function_name):
        return jsonify({"error": "Provide at least 'goal' or both 'function_name' and 'tests'"}), 400

    result = orc.run(goal=goal, user_tests=user_tests, function_name=function_name, max_iters=max_iters)
    status_code = 200 if result.get("success") else 422
    return jsonify(result), status_code

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app


@app.route('/agents/planner', methods=['POST'])
def _auto_stub_agents_planner():
    return 'Auto-generated stub for /agents/planner', 200
