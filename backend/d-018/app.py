import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from typing import Any, Dict
from storage import Storage
from models import Runner, JobRequest
from router import select_runner
from config import DEFAULT_POLICY, STORAGE_FILE

app = Flask(__name__)

store = Storage(os.getenv("STORAGE_FILE", STORAGE_FILE))

# Ensure initial structure
if not store.exists():
    store.save({
        "runners": [],
        "policy": DEFAULT_POLICY,
    })


def parse_json() -> Dict[str, Any]:
    if not request.data:
        return {}
    try:
        return request.get_json(force=True, silent=False) or {}
    except Exception:
        return {}


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/runners")
def list_runners():
    data = store.load()
    return jsonify({
        "runners": data.get("runners", []),
        "count": len(data.get("runners", []))
    })


@app.post("/runners")
def create_runner():
    body = parse_json()
    try:
        runner = Runner.from_dict(body)
        runner = store.add_runner(runner.to_dict())
        return jsonify(runner), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.patch("/runners/<runner_id>")
def update_runner(runner_id: str):
    body = parse_json()
    try:
        updated = store.update_runner(runner_id, body)
        if not updated:
            return jsonify({"error": "Runner not found"}), 404
        return jsonify(updated)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.delete("/runners/<runner_id>")
def delete_runner(runner_id: str):
    ok = store.delete_runner(runner_id)
    if not ok:
        return jsonify({"error": "Runner not found"}), 404
    return ("", 204)


@app.get("/policy")
def get_policy():
    data = store.load()
    return jsonify(data.get("policy", DEFAULT_POLICY))


@app.post("/policy")
def set_policy():
    body = parse_json()
    if not isinstance(body, dict):
        return jsonify({"error": "Invalid policy body"}), 400
    # Merge shallowly with existing policy
    existing = store.load().get("policy", DEFAULT_POLICY)
    merged = {**existing, **body}
    store.set_policy(merged)
    return jsonify(merged)


@app.post("/route")
def route_job():
    body = parse_json()
    try:
        job = JobRequest.from_dict(body)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = store.load()
    runners = [Runner.from_dict(r) for r in data.get("runners", [])]
    policy = data.get("policy", DEFAULT_POLICY)

    decision = select_runner(job, runners, policy)

    status = 200 if decision.get("selected") else 409
    return jsonify(decision), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))



def create_app():
    return app
