import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from planning_agent.agent import PlanningAgent
from planning_agent.storage import PlanStore
from planning_agent.models import ChecklistUpdateRequest

app = Flask(__name__)
store = PlanStore()
agent = PlanningAgent(store)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/api/plan', methods=['POST'])
def create_plan():
    data = request.get_json(force=True, silent=True) or {}
    goal = data.get('goal')
    if not goal or not isinstance(goal, str):
        return jsonify({"error": "Field 'goal' (string) is required"}), 400
    context = data.get('context') or ""
    constraints = data.get('constraints') or []
    preferences = data.get('preferences') or {}
    plan = agent.generate_plan(goal=goal, context=context, constraints=constraints, preferences=preferences)
    return jsonify({
        "plan_id": plan.plan_id,
        "plan": plan.to_dict(),
        "manifest": plan.manifest
    })

@app.route('/api/plan/<plan_id>', methods=['GET'])
def get_plan(plan_id: str):
    plan = store.get(plan_id)
    if not plan:
        return jsonify({"error": "plan not found"}), 404
    return jsonify({
        "plan_id": plan.plan_id,
        "status": plan.status,
        "plan": plan.to_dict(),
        "manifest": plan.manifest
    })

@app.route('/api/plan/<plan_id>/approve', methods=['POST'])
def approve_plan(plan_id: str):
    plan = store.get(plan_id)
    if not plan:
        return jsonify({"error": "plan not found"}), 404
    if plan.status not in ["draft", "halted"]:
        return jsonify({"error": f"cannot approve from status '{plan.status}'"}), 400
    plan.status = "approved"
    store.save(plan)
    return jsonify({"plan_id": plan.plan_id, "status": plan.status})

@app.route('/api/plan/<plan_id>/checklist', methods=['POST'])
def update_checklist(plan_id: str):
    plan = store.get(plan_id)
    if not plan:
        return jsonify({"error": "plan not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    try:
        update_req = ChecklistUpdateRequest.from_dict(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    updated = agent.update_checklist_items(plan, update_req)
    store.save(plan)
    return jsonify({
        "plan_id": plan.plan_id,
        "updated": updated,
        "plan": plan.to_dict()
    })

@app.route('/api/plan/<plan_id>/execute', methods=['POST'])
def execute_plan(plan_id: str):
    plan = store.get(plan_id)
    if not plan:
        return jsonify({"error": "plan not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    stepwise = bool(data.get('stepwise', False))
    if plan.status not in ["approved", "executing", "halted"]:
        return jsonify({"error": f"plan not in executable state: {plan.status}"}), 400
    result = agent.execute(plan, stepwise=stepwise)
    store.save(plan)
    status_code = 200
    if result.get("halted"):
        status_code = 409
    return jsonify(result), status_code

@app.route('/api/plan/<plan_id>/status', methods=['GET'])
def status(plan_id: str):
    plan = store.get(plan_id)
    if not plan:
        return jsonify({"error": "plan not found"}), 404
    return jsonify(agent.status(plan))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)



def create_app():
    return app
