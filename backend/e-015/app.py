import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import os
import signal
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request, abort

from config import Config
from graceful import LifecycleManager
from imds import SpotInterruptionWatcher
from job_queue import JobQueue
from worker import WorkerThread


app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
)
logger = logging.getLogger("spot.app")

# Load configuration
config = Config.from_env()

# Global components
lifecycle = LifecycleManager(grace_period_seconds=config.GRACE_PERIOD_SECONDS)
queue = JobQueue(config.DATABASE_URL)
queue.reset_stale_processing()

stop_event = threading.Event()
worker = WorkerThread(
    job_queue=queue,
    stop_event=stop_event,
    drain_event=lifecycle.draining_event,
    per_job_seconds=config.JOB_PROCESSING_SECONDS,
    heartbeat_interval=1.0,
)
worker.daemon = True
worker.start()

# Start IMDS watcher if enabled
if config.SPOT_WATCHER_ENABLED:
    watcher = SpotInterruptionWatcher(
        lifecycle=lifecycle,
        poll_interval=config.POLL_INTERVAL_SECONDS,
        imds_url=config.IMDS_URL,
    )
    watcher.daemon = True
    watcher.start()

# Register signal handlers
lifecycle.install_signal_handlers()


@app.before_request
def reject_writes_when_draining():
    # Optionally reject job creation on drain
    if request.method in ("POST", "PUT", "PATCH") and lifecycle.is_draining():
        abort(503, description="Draining: instance preparing to terminate; try another instance.")


@app.route("/health", methods=["GET"])
def health():
    # Liveness probe: process is up regardless of draining
    return jsonify({
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "draining": lifecycle.is_draining(),
    })


@app.route("/ready", methods=["GET"])
def ready():
    # Readiness probe: return 200 if not draining
    if lifecycle.is_draining():
        return jsonify({
            "status": "draining",
            "message": "Instance is draining and should be deregistered from LB",
        }), 503
    return jsonify({
        "status": "ready",
        "worker_alive": worker.is_alive(),
    })


@app.route("/jobs", methods=["POST"])
def create_job():
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        abort(400, description="Invalid JSON payload")
    if payload is None:
        abort(400, description="Missing JSON payload")

    job_id = queue.enqueue(payload)
    return jsonify({"job_id": job_id}), 201


@app.route("/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id: int):
    job = queue.get_job(job_id)
    if not job:
        abort(404, description="Job not found")
    return jsonify(job)


@app.route("/metrics", methods=["GET"])
def metrics():
    counts = queue.metrics()
    return jsonify({
        "draining": lifecycle.is_draining(),
        "counts": counts,
        "worker_alive": worker.is_alive(),
    })


@app.route("/simulate/interruption", methods=["POST"])
def simulate_interruption():
    if not config.ALLOW_SIMULATE_INTERRUPTION:
        abort(403, description="Simulation disabled")

    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "simulated")
    logger.warning("Simulating interruption: %s", reason)
    lifecycle.initiate_draining(source=f"simulation:{reason}")
    return jsonify({"status": "draining", "reason": reason})


@app.route("/drain", methods=["POST"])
def drain_manual():
    # Manual drain endpoint (e.g., preStop hook)
    lifecycle.initiate_draining(source="manual")
    return jsonify({"status": "draining"})


@app.route("/shutdown", methods=["POST"])
def shutdown_now():
    # Force an immediate shutdown (if allowed)
    if not config.ALLOW_SIMULATE_INTERRUPTION:
        abort(403, description="Shutdown disabled")
    logger.warning("Forced shutdown requested via /shutdown")
    threading.Thread(target=_graceful_exit, name="ForcedShutdown", daemon=True).start()
    return jsonify({"status": "shutting_down"})


def _graceful_exit():
    lifecycle.initiate_draining(source="forced")
    # Wait briefly for in-flight job
    time.sleep(min(5, config.GRACE_PERIOD_SECONDS))
    stop_event.set()
    os._exit(0)


if __name__ == "__main__":
    # Start Flask app
    # Use a single process server when running bundled worker threads
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    app.run(host=host, port=port)



def create_app():
    return app


@app.route('/spot-strategy', methods=['GET'])
def _auto_stub_spot_strategy():
    return 'Auto-generated stub for /spot-strategy', 200
