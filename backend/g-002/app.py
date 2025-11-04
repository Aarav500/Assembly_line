import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, send_file, abort
import os
import json

import config
import db
import storage

app = Flask(__name__)

# Ensure DB initialized for Flask context too
with app.app_context():
    db.init_db()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/jobs", methods=["POST"])
def create_job():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    epochs = int(data.get("epochs", config.DEFAULT_EPOCHS))
    checkpoint_interval = int(data.get("checkpoint_interval", config.DEFAULT_CHECKPOINT_INTERVAL))
    max_retries = int(data.get("max_retries", config.DEFAULT_MAX_RETRIES))
    # Any extra params are allowed
    params = dict(data)
    params["epochs"] = epochs
    params["checkpoint_interval"] = checkpoint_interval

    job_chkpt_dir, log_path = storage.ensure_job_dirs("pending")
    # We will fix the directory name after we have the job_id; create now for guarantee directories exist

    # Create job
    job_id = db.create_job(params=params, name=name, total_epochs=epochs, checkpoint_path="", log_path="", max_retries=max_retries)

    # Fix directories for this job
    chkpt_dir, log_path = storage.ensure_job_dirs(job_id)
    db.update_job_fields(job_id, {"checkpoint_path": chkpt_dir, "log_path": log_path})

    return jsonify({"job_id": job_id}), 201


@app.route("/jobs", methods=["GET"])
def list_jobs():
    items = db.list_jobs(limit=int(request.args.get("limit", 100)))
    # Attach attempts count
    for j in items:
        j["attempts"] = len(db.get_attempts(j["id"]))
        try:
            j["params"] = json.loads(j["params"]) if j.get("params") else {}
        except Exception:
            j["params"] = {}
    return jsonify(items)


@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    row = db.get_job(job_id)
    if not row:
        abort(404)
    try:
        row["params"] = json.loads(row["params"]) if row.get("params") else {}
    except Exception:
        row["params"] = {}
    row["attempts"] = db.get_attempts(job_id)
    row["checkpoints"] = storage.list_checkpoints(job_id)
    return jsonify(row)


@app.route("/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    row = db.get_job(job_id)
    if not row:
        abort(404)
    if row.get("status") in ("completed", "failed", "canceled"):
        return jsonify({"status": row.get("status"), "message": "Job already finalized"}), 200
    db.request_cancel(job_id)
    return jsonify({"status": "cancel_requested"})


@app.route("/jobs/<job_id>/logs", methods=["GET"])
def get_logs(job_id):
    row = db.get_job(job_id)
    if not row:
        abort(404)
    log_path = row.get("log_path")
    content = storage.read_log(log_path)
    return jsonify({"log": content})


@app.route("/jobs/<job_id>/checkpoints", methods=["GET"])
def list_checkpoints(job_id):
    if not db.get_job(job_id):
        abort(404)
    return jsonify(storage.list_checkpoints(job_id))


if __name__ == "__main__":
    # For direct run of app.py, no orchestrator is started here to avoid multiprocess conflicts.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False, use_reloader=False)



def create_app():
    return app


@app.route('/autoscale', methods=['POST'])
def _auto_stub_autoscale():
    return 'Auto-generated stub for /autoscale', 200
