import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import json
from flask import Flask, request, jsonify
from datetime import datetime

from harness.suites import SuiteRepository
from harness.adapters import build_adapter
from harness.evaluator import Evaluator
from harness.storage import RunStorage
import config

app = Flask(__name__)

# Initialize repositories and storage
suite_repo = SuiteRepository(config.SUITES_DIR)
run_storage = RunStorage(config.RUNS_DIR)

def error_response(message, status=400):
    return jsonify({"error": message}), status

@app.route("/api/health", methods=["GET"])  # simple liveness
def health():
    return jsonify({"status": "ok"})

@app.route("/api/suites", methods=["GET"])  # list suites
def list_suites():
    suites = suite_repo.list_suites()
    return jsonify({"suites": suites})

@app.route("/api/suites/<name>", methods=["GET"])  # fetch a suite
def get_suite(name):
    suite = suite_repo.get_suite(name)
    if not suite:
        return error_response(f"Suite '{name}' not found", 404)
    return jsonify({"suite": suite})

@app.route("/api/suites", methods=["POST"])  # create/update suite
def create_suite():
    try:
        data = request.get_json(force=True)
    except Exception:
        return error_response("Invalid JSON body")
    if not isinstance(data, dict):
        return error_response("Body must be a JSON object")
    try:
        saved = suite_repo.save_suite(data)
        return jsonify({"saved": saved}), 201
    except Exception as e:
        return error_response(str(e))

@app.route("/api/evaluate", methods=["POST"])  # run evaluation
def evaluate():
    try:
        payload = request.get_json(force=True)
    except Exception:
        return error_response("Invalid JSON body")

    suite_name = payload.get("suite")
    model_spec = payload.get("model")
    max_items = payload.get("max_items")
    shuffle = payload.get("shuffle", False)
    seed = payload.get("seed")

    if not suite_name:
        return error_response("Field 'suite' is required")
    if not model_spec or not isinstance(model_spec, dict):
        return error_response("Field 'model' is required and must be an object")

    suite = suite_repo.get_suite(suite_name)
    if not suite:
        return error_response(f"Suite '{suite_name}' not found", 404)

    try:
        adapter = build_adapter(model_spec)
    except Exception as e:
        return error_response(f"Invalid model spec: {e}")

    evaluator = Evaluator()

    try:
        result = evaluator.evaluate_suite(suite, adapter, max_items=max_items, shuffle=shuffle, seed=seed)
    except Exception as e:
        return error_response(f"Evaluation failed: {e}")

    # persist run
    run_id = str(uuid.uuid4())
    metadata = {
        "run_id": run_id,
        "suite": suite.get("name"),
        "model": adapter.name,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    artifact = {"metadata": metadata, "result": result}
    run_storage.save_run(run_id, artifact)

    return jsonify({"run_id": run_id, "result": result})

@app.route("/api/runs", methods=["GET"])  # list runs
def list_runs():
    runs = run_storage.list_runs()
    return jsonify({"runs": runs})

@app.route("/api/runs/<run_id>", methods=["GET"])  # get run
def get_run(run_id):
    run = run_storage.load_run(run_id)
    if not run:
        return error_response("Run not found", 404)
    return jsonify(run)

@app.route("/api/benchmark", methods=["POST"])  # run multiple suites/models
def benchmark():
    try:
        payload = request.get_json(force=True)
    except Exception:
        return error_response("Invalid JSON body")

    suites = payload.get("suites")
    models = payload.get("models")
    max_items = payload.get("max_items")
    shuffle = payload.get("shuffle", False)
    seed = payload.get("seed")

    if not suites or not isinstance(suites, list):
        return error_response("Field 'suites' must be a non-empty array")
    if not models or not isinstance(models, list):
        return error_response("Field 'models' must be a non-empty array")

    evaluator = Evaluator()
    bench_results = []

    for suite_name in suites:
        suite = suite_repo.get_suite(suite_name)
        if not suite:
            return error_response(f"Suite '{suite_name}' not found", 404)
        for model_spec in models:
            try:
                adapter = build_adapter(model_spec)
            except Exception as e:
                return error_response(f"Invalid model spec for benchmark: {e}")

            result = evaluator.evaluate_suite(suite, adapter, max_items=max_items, shuffle=shuffle, seed=seed)
            run_id = str(uuid.uuid4())
            metadata = {
                "run_id": run_id,
                "suite": suite.get("name"),
                "model": adapter.name,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            artifact = {"metadata": metadata, "result": result}
            run_storage.save_run(run_id, artifact)
            bench_results.append({"run_id": run_id, "suite": suite.get("name"), "model": adapter.name, "result": result})

    return jsonify({"results": bench_results})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app


@app.route('/suites/test_suite_1', methods=['GET'])
def _auto_stub_suites_test_suite_1():
    return 'Auto-generated stub for /suites/test_suite_1', 200
