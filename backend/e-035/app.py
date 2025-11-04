import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
from flask import Flask, jsonify, request

from config import SERVICES
from pipeline import PipelineRunner, compute_channel, parse_dockerfile_base, update_available_for_service
from storage import Storage

app = Flask(__name__)

storage = Storage()
runner = PipelineRunner(storage=storage)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/services", methods=["GET"])
def list_services():
    services = []
    for svc in SERVICES:
        dockerfile = svc["dockerfile"]
        base = parse_dockerfile_base(dockerfile)
        upd = update_available_for_service(svc, base)
        services.append({
            "name": svc["name"],
            "dockerfile": dockerfile,
            "current_base": base,
            "channel": compute_channel(base.split(":", 1)[1]) if ":" in base else None,
            "update": upd,
        })
    return jsonify({"services": services})


@app.route("/config", methods=["GET"])
def get_config():
    return jsonify({"services": SERVICES})


@app.route("/runs", methods=["GET"])
def list_runs():
    return jsonify({"runs": storage.list_runs()})


@app.route("/runs/<run_id>", methods=["GET"])
def get_run(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify({"error": "not_found"}), 404
    return jsonify(run)


@app.route("/trigger/<service_name>", methods=["POST"]) 
def trigger(service_name):
    svc = next((s for s in SERVICES if s["name"] == service_name), None)
    if not svc:
        return jsonify({"error": "service_not_found"}), 404

    base = parse_dockerfile_base(svc["dockerfile"]) or svc.get("base_image")
    upd = update_available_for_service(svc, base)
    if not upd or not upd.get("update_available"):
        return jsonify({"message": "no_update", "current_base": base}), 200

    run = runner.create_and_start_run(service=svc, current_base=base, target_base=upd["target_base"])
    return jsonify(run), 201


@app.route("/approve/<run_id>", methods=["POST"]) 
def approve(run_id):
    run = storage.get_run(run_id)
    if not run:
        return jsonify({"error": "not_found"}), 404
    if run.get("status") != "waiting_approval":
        return jsonify({"message": "not_waiting", "status": run.get("status")}), 400
    storage.set_run_field(run_id, "approved", True)
    # resume asynchronously
    threading.Thread(target=runner.resume_run, args=(run_id,), daemon=True).start()
    return jsonify({"message": "approved", "run_id": run_id})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/images', methods=['GET'])
def _auto_stub_images():
    return 'Auto-generated stub for /images', 200


@app.route('/images/python', methods=['GET'])
def _auto_stub_images_python():
    return 'Auto-generated stub for /images/python', 200


@app.route('/images/invalid', methods=['GET'])
def _auto_stub_images_invalid():
    return 'Auto-generated stub for /images/invalid', 200


@app.route('/images/node', methods=['POST'])
def _auto_stub_images_node():
    return 'Auto-generated stub for /images/node', 200


@app.route('/safety-gates', methods=['GET'])
def _auto_stub_safety_gates():
    return 'Auto-generated stub for /safety-gates', 200
