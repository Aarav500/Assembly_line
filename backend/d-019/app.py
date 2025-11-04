import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, abort
from job_queue import JobQueue, Worker

app = Flask(__name__)

queue = JobQueue()
worker = Worker(queue)
worker.start()


def _validate_policy(data):
    if data is None:
        return {}
    allowed = {
        "timeout_seconds": (int, float),
        "max_attempts": int,
        "backoff_initial_seconds": (int, float),
        "backoff_multiplier": (int, float),
        "backoff_max_seconds": (int, float),
        "jitter_seconds": (int, float),
    }
    policy = {}
    for k, t in allowed.items():
        if k in data:
            v = data[k]
            if not isinstance(v, t):
                abort(400, description=f"policy.{k} must be {t}")
            policy[k] = float(v) if isinstance(v, (int, float)) else v
    return policy


@app.route("/jobs", methods=["POST"])
def submit_job():
    payload = request.get_json(force=True, silent=False)
    if not payload or "task" not in payload:
        abort(400, description="Missing 'task' field")
    task_name = payload["task"]
    params = payload.get("params", {})
    if params is not None and not isinstance(params, dict):
        abort(400, description="'params' must be a JSON object")
    policy = _validate_policy(payload.get("policy"))
    try:
        job = queue.submit(task_name=task_name, params=params, policy=policy)
    except ValueError as e:
        abort(400, description=str(e))
    return jsonify(job.to_dict()), 201


@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    job = queue.get(job_id)
    if not job:
        abort(404)
    return jsonify(job.to_dict())


@app.route("/jobs", methods=["GET"])
def list_jobs():
    status = request.args.get("status")
    jobs = queue.list(status=status)
    return jsonify([j.to_dict(summary=True) for j in jobs])


@app.route("/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    ok = queue.cancel(job_id)
    if not ok:
        abort(404)
    job = queue.get(job_id)
    return jsonify(job.to_dict())


if __name__ == "__main__":
    # For direct execution: flask run alternative
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app
