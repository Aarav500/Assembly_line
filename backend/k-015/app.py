import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
from flask import Flask, request, jsonify
from storage import Storage
from run_loop import step_run, auto_run
from agent import get_model

app = Flask(__name__)
storage = Storage()

# Simple in-process lock to avoid concurrent mutation of the same run
run_locks = {}
locks_lock = threading.Lock()

def get_run_lock(run_id: str) -> threading.Lock:
    with locks_lock:
        if run_id not in run_locks:
            run_locks[run_id] = threading.Lock()
        return run_locks[run_id]

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/runs', methods=['POST'])
def create_run():
    data = request.get_json(force=True) or {}
    initial_prompt = data.get('initial_prompt')
    if not initial_prompt or not isinstance(initial_prompt, str):
        return jsonify({"error": "initial_prompt (string) is required"}), 400

    criteria = data.get('criteria') or []
    if not isinstance(criteria, list) or not all(isinstance(c, str) for c in criteria):
        return jsonify({"error": "criteria must be a list of strings"}), 400

    target_score = data.get('target_score', 0.9)
    try:
        target_score = float(target_score)
    except Exception:
        return jsonify({"error": "target_score must be a float"}), 400

    max_iterations = data.get('max_iterations', 5)
    try:
        max_iterations = int(max_iterations)
    except Exception:
        return jsonify({"error": "max_iterations must be an integer"}), 400

    model_spec = data.get('model', 'dummy')
    temperature = data.get('temperature', 0.2)

    run = storage.create_run({
        'initial_prompt': initial_prompt,
        'current_prompt': initial_prompt,
        'criteria': criteria,
        'target_score': target_score,
        'max_iterations': max_iterations,
        'model': model_spec,
        'temperature': temperature,
    })
    return jsonify(run)

@app.route('/runs', methods=['GET'])
def list_runs():
    runs = storage.list_runs()
    return jsonify(runs)

@app.route('/runs/<run_id>', methods=['GET'])
def get_run(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    return jsonify(run)

@app.route('/runs/<run_id>/step', methods=['POST'])
def run_step(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404

    lock = get_run_lock(run_id)
    with lock:
        # reload run inside lock to avoid stale view
        run = storage.get_run(run_id)
        if run['status'] in ['completed', 'failed', 'stopped']:
            return jsonify(run)
        model = get_model(run.get('model', 'dummy'), temperature=run.get('temperature', 0.2))
        updated_run = step_run(run, model)
        storage.update_run(updated_run)
        return jsonify(updated_run)

@app.route('/runs/<run_id>/auto', methods=['POST'])
def run_auto(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404

    lock = get_run_lock(run_id)
    with lock:
        run = storage.get_run(run_id)
        if run['status'] in ['completed', 'failed', 'stopped']:
            return jsonify(run)
        model = get_model(run.get('model', 'dummy'), temperature=run.get('temperature', 0.2))
        updated_run = auto_run(run, model)
        storage.update_run(updated_run)
        return jsonify(updated_run)

@app.route('/runs/<run_id>/stop', methods=['POST'])
def stop_run(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    lock = get_run_lock(run_id)
    with lock:
        run = storage.get_run(run_id)
        run['status'] = 'stopped'
        storage.update_run(run)
        return jsonify(run)

@app.route('/runs/<run_id>/reset', methods=['POST'])
def reset_run(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    lock = get_run_lock(run_id)
    with lock:
        run = storage.get_run(run_id)
        run['iterations'] = []
        run['current_prompt'] = run['initial_prompt']
        run['status'] = 'pending'
        storage.update_run(run)
        return jsonify(run)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)



def create_app():
    return app
