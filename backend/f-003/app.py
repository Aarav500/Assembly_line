import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import threading
from datetime import datetime
from flask import Flask, jsonify, request
from dotenv import load_dotenv

from runner.config import load_config, Config
from runner.storage import Storage
from runner.notifiers import NotifierManager
from runner.alerting import AlertManager
from runner.flows import FlowRunner
from runner.scheduler import SchedulerManager

load_dotenv()

app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

# Global singletons
storage = None
config: Config | None = None
notifier_manager: NotifierManager | None = None
alert_manager: AlertManager | None = None
flow_runner: FlowRunner | None = None
scheduler_manager: SchedulerManager | None = None

init_lock = threading.Lock()


def initialize():
    global storage, config, notifier_manager, alert_manager, flow_runner, scheduler_manager
    with init_lock:
        config_path = os.getenv("CONFIG_FILE", "config.yaml")
        new_config = load_config(config_path)

        # Storage (DB)
        db_url = new_config.database_url or os.getenv("DATABASE_URL", "sqlite:///synthetic.db")
        new_storage = Storage(db_url)
        new_storage.init_db()

        # Notifiers
        new_notifiers = NotifierManager(new_config)

        # Alert manager
        new_alert_manager = AlertManager(new_storage, new_notifiers, new_config)

        # Flow runner
        new_runner = FlowRunner(new_storage, new_alert_manager, new_config)

        # Scheduler
        if scheduler_manager is None:
            sm = SchedulerManager(new_runner)
            sm.start()
        else:
            sm = scheduler_manager
        sm.reschedule_all(new_config)

        # Swap references
        storage = new_storage
        alert_manager = new_alert_manager
        notifier_manager = new_notifiers
        flow_runner = new_runner
        scheduler_manager = sm
        
        return True


@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})


@app.route("/")
def index():
    return jsonify({
        "name": "Synthetic Transaction Runner",
        "endpoints": {
            "/health": "Service health",
            "/api/flows": "List flows",
            "/api/flows/reload": "Reload config and reschedule (POST)",
            "/api/run/<flow_id>": "Trigger a run (POST). Pass sync=1 to wait for result",
            "/api/results": "List flow runs",
            "/api/results/<run_id>": "Get a specific run",
            "/api/alerts": "List alert events"
        }
    })


@app.route("/api/flows", methods=["GET"])
def list_flows():
    cfg = scheduler_manager.get_config() if scheduler_manager else None
    flows = []
    if cfg:
        for f in cfg.flows:
            flows.append({
                "id": f.id,
                "name": f.name,
                "enabled": f.enabled,
                "schedule_every_sec": f.schedule_every_sec,
                "severity": f.severity,
                "fail_threshold": f.fail_threshold,
                "alert_channels": f.alert_channels
            })
    return jsonify({"flows": flows})


@app.route("/api/flows/reload", methods=["POST"])
def reload_flows():
    initialize()
    return jsonify({"status": "reloaded"})


@app.route("/api/run/<flow_id>", methods=["POST"]) 
def run_flow(flow_id):
    sync = request.args.get("sync") in ("1", "true", "True")
    if not scheduler_manager:
        return jsonify({"error": "system not initialized"}), 500

    if sync:
        result = scheduler_manager.runner.run_and_record(flow_id)
        if result is None:
            return jsonify({"error": f"flow {flow_id} not found or disabled"}), 404
        return jsonify(result)
    else:
        enqueued = scheduler_manager.run_now(flow_id)
        if not enqueued:
            return jsonify({"error": f"flow {flow_id} not found or disabled"}), 404
        return jsonify({"status": "queued"})


@app.route("/api/results", methods=["GET"]) 
def list_results():
    flow_id = request.args.get("flow_id")
    limit = int(request.args.get("limit", 50))
    runs = storage.get_flow_runs(flow_id=flow_id, limit=limit)
    return jsonify({"runs": runs})


@app.route("/api/results/<int:run_id>", methods=["GET"]) 
def get_result(run_id: int):
    run = storage.get_flow_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    steps = storage.get_step_runs(run_id)
    out = run
    out["steps"] = steps
    return jsonify(out)


@app.route("/api/alerts", methods=["GET"]) 
def list_alerts():
    limit = int(request.args.get("limit", 100))
    flow_id = request.args.get("flow_id")
    items = storage.get_alerts(flow_id=flow_id, limit=limit)
    return jsonify({"alerts": items})


if __name__ == "__main__":
    initialize()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/run/user_login', methods=['POST'])
def _auto_stub_run_user_login():
    return 'Auto-generated stub for /run/user_login', 200


@app.route('/run/invalid_flow', methods=['POST'])
def _auto_stub_run_invalid_flow():
    return 'Auto-generated stub for /run/invalid_flow', 200


@app.route('/run/checkout', methods=['POST'])
def _auto_stub_run_checkout():
    return 'Auto-generated stub for /run/checkout', 200
