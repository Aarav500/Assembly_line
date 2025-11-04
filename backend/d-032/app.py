import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, abort, send_from_directory
from util.repo_manager import RepoManager


def create_app():
    app = Flask(__name__)
    repo_path = os.environ.get("REPO_PATH", "./repo")
    app.config["REPO_PATH"] = repo_path
    app.config["APP_NAME"] = os.environ.get("APP_NAME", "Canary Analysis Dashboard")

    repo = RepoManager(repo_path)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/")
    def index():
        runs = repo.list_runs()
        runs_sorted = sorted(runs, key=lambda r: r.get("timestamp", ""), reverse=True)
        return render_template("index.html", runs=runs_sorted, app_name=app.config["APP_NAME"])

    @app.route("/runs/<run_id>")
    def run_detail(run_id):
        run = repo.get_run(run_id)
        if not run:
            abort(404)
        log_lines = repo.get_log_lines(run_id)
        return render_template("run.html", run=run, log_lines=log_lines, app_name=app.config["APP_NAME"]) 

    @app.route("/logs")
    def logs_index():
        logs = repo.list_logs()
        return render_template("logs.html", logs=logs, app_name=app.config["APP_NAME"])

    @app.route("/logs/<run_id>.log")
    def get_log(run_id):
        logs_dir = repo.logs_dir
        log_filename = f"{run_id}.log"
        if not os.path.isfile(os.path.join(logs_dir, log_filename)):
            abort(404)
        return send_from_directory(logs_dir, log_filename, as_attachment=False, mimetype="text/plain")

    # API
    @app.route("/api/runs", methods=["GET"]) 
    def api_list_runs():
        return jsonify(repo.list_runs())

    @app.route("/api/runs/<run_id>", methods=["GET"]) 
    def api_get_run(run_id):
        run = repo.get_run(run_id)
        if not run:
            abort(404)
        return jsonify(run)

    @app.route("/api/runs", methods=["POST"]) 
    def api_create_run():
        payload = request.get_json(force=True, silent=False)
        if not isinstance(payload, dict):
            abort(400)
        run_id = payload.get("id") or str(uuid.uuid4())
        run_id = repo.sanitize_id(run_id)
        now = datetime.now(timezone.utc).isoformat()

        # Build run object with sensible defaults
        run = {
            "id": run_id,
            "service": payload.get("service", "unknown-service"),
            "timestamp": payload.get("timestamp", now),
            "baseline": payload.get("baseline", {}),
            "canary": payload.get("canary", {}),
            "metrics": payload.get("metrics", []),
            "aggregate_score": payload.get("aggregate_score", None),
            "thresholds": payload.get("thresholds", {"pass": 90, "warn": 75}),
            "decision": payload.get("decision", {"result": "pending", "reason": ""}),
            "metadata": payload.get("metadata", {}),
        }

        repo.save_run(run, commit_message=f"Add canary run {run_id}")
        return jsonify(run), 201

    @app.route("/api/runs/<run_id>/decision", methods=["POST"]) 
    def api_decision(run_id):
        payload = request.get_json(force=True, silent=False)
        if not isinstance(payload, dict):
            abort(400)
        run = repo.get_run(run_id)
        if not run:
            abort(404)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": payload.get("user", "unknown"),
            "result": payload.get("result", "pending"),
            "reason": payload.get("reason", ""),
            "metadata": payload.get("metadata", {}),
        }
        # Update run decision to latest
        run["decision"] = {k: entry[k] for k in ["timestamp", "result", "reason"]}
        repo.save_run(run, commit_message=f"Update decision for {run_id}: {entry['result']}")
        repo.append_log(run_id, entry, commit_message=f"Decision log for {run_id}: {entry['result']}")
        return jsonify({"status": "ok", "entry": entry})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



@app.route('/api/deployments', methods=['GET', 'POST'])
def _auto_stub_api_deployments():
    return 'Auto-generated stub for /api/deployments', 200


@app.route('/api/decision-logs', methods=['GET', 'POST'])
def _auto_stub_api_decision_logs():
    return 'Auto-generated stub for /api/decision-logs', 200
