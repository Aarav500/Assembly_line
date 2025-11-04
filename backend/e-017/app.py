import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import signal
import threading
import time
from flask import Flask, jsonify, request

from config import AppConfig
from lease_manager import LeaseManager
from rotation_scheduler import RotationScheduler
from vault_manager import VaultManager

app = Flask(__name__)

config = AppConfig()

vault = VaultManager(
    address=config.vault_addr,
    token=config.vault_token,
    namespace=config.vault_namespace,
    auth_method=config.vault_auth_method,
    k8s_role=config.vault_k8s_role,
    k8s_jwt_path=config.kubernetes_jwt_path,
)

lease_manager = LeaseManager(vault_manager=vault)
rotation_scheduler = RotationScheduler(vault_manager=vault)

# Load rotation jobs from config file if present
if config.rotation_jobs:
    rotation_scheduler.load_jobs(config.rotation_jobs)


@app.route("/healthz", methods=["GET"])  # liveness
@app.route("/readyz", methods=["GET"])   # readiness
@app.route("/livez", methods=["GET"])    # alias
@app.route("/status", methods=["GET"])   # alias
def healthz():
    return jsonify({"status": "ok", "vault_authenticated": vault.is_authenticated()}), 200


@app.route("/leases", methods=["GET"])
def list_leases():
    return jsonify({
        "count": lease_manager.count(),
        "leases": lease_manager.snapshot()
    }), 200


@app.route("/leases/<path:lease_id>", methods=["DELETE"])  
def revoke_lease(lease_id):
    found = lease_manager.get(lease_id)
    try:
        vault.revoke_lease(lease_id)
        lease_manager.remove(lease_id)
        return jsonify({"revoked": True, "lease_id": lease_id, "found": found is not None}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/kv/<path:secret_path>", methods=["GET"])  
def get_kv(secret_path):
    mount = request.args.get("mount", default=config.vault_mount_kv, type=str)
    version = request.args.get("version", default=None, type=int)
    try:
        data, metadata = vault.read_kv_secret(path=secret_path, mount_point=mount, version=version)
        return jsonify({"path": secret_path, "mount": mount, "data": data, "metadata": metadata}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/kv/<path:secret_path>", methods=["POST"])  
def write_kv(secret_path):
    mount = request.args.get("mount", default=config.vault_mount_kv, type=str)
    payload = request.get_json(silent=True) or {}
    data = payload.get("data")
    if not isinstance(data, dict):
        return jsonify({"error": "Body must be JSON with 'data' object"}), 400
    try:
        metadata = vault.write_kv_secret(path=secret_path, data=data, mount_point=mount)
        return jsonify({"path": secret_path, "mount": mount, "metadata": metadata}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/kv/<path:secret_path>/rotate", methods=["POST"])  
def rotate_kv(secret_path):
    mount = request.args.get("mount", default=config.vault_mount_kv, type=str)
    payload = request.get_json(silent=True) or {}
    field = payload.get("field", "password")
    length = int(payload.get("length", 32))
    alphabet = payload.get("alphabet")
    preserve_fields = payload.get("preserve_fields", {})
    try:
        new_value, metadata = vault.rotate_kv_random_secret(
            path=secret_path,
            field=field,
            length=length,
            mount_point=mount,
            alphabet=alphabet,
            preserve_fields=preserve_fields,
        )
        return jsonify({
            "path": secret_path,
            "mount": mount,
            "rotated_field": field,
            "length": length,
            "new_value_preview": new_value[:4] + "***",
            "metadata": metadata,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/dynamic/<string:role>", methods=["GET"])  
def get_dynamic_secret(role):
    mount = request.args.get("mount", default=config.vault_mount_database, type=str)
    try:
        secret = vault.generate_database_credentials(role=role, mount_point=mount)
        lease_manager.add(
            lease_id=secret["lease_id"],
            lease_duration=secret.get("lease_duration", 0),
            renewable=secret.get("renewable", False),
            meta={"mount": mount, "role": role}
        )
        response = {
            "lease_id": secret.get("lease_id"),
            "lease_duration": secret.get("lease_duration"),
            "renewable": secret.get("renewable"),
            "data": secret.get("data", {}),
            "warnings": secret.get("warnings"),
        }
        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/rotate/database-root", methods=["POST"])  
def rotate_database_root():
    payload = request.get_json(silent=True) or {}
    mount = payload.get("mount", config.vault_mount_database)
    connection = payload.get("connection")
    if not connection:
        return jsonify({"error": "Missing 'connection' in body"}), 400
    try:
        vault.rotate_database_root(mount_point=mount, connection_name=connection)
        return jsonify({"rotated": True, "mount": mount, "connection": connection}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/scheduler/jobs", methods=["GET"])  
def list_jobs():
    return jsonify({"jobs": rotation_scheduler.describe_jobs()}), 200


@app.route("/scheduler/jobs", methods=["POST"])  
def add_job():
    job = request.get_json(silent=True) or {}
    try:
        jid = rotation_scheduler.add_job(job)
        return jsonify({"id": jid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.before_first_request
def startup_background_threads():
    if not vault.is_authenticated():
        vault.authenticate()
    lease_manager.start()
    rotation_scheduler.start()


def shutdown_handler(*_args):
    rotation_scheduler.stop()
    lease_manager.stop()
    # give threads a moment to exit gracefully
    time.sleep(0.2)
    os._exit(0)


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


if __name__ == "__main__":
    # Eager init when running directly
    if not vault.is_authenticated():
        vault.authenticate()
    lease_manager.start()
    rotation_scheduler.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))



def create_app():
    return app


@app.route('/secrets/rotate', methods=['POST'])
def _auto_stub_secrets_rotate():
    return 'Auto-generated stub for /secrets/rotate', 200
