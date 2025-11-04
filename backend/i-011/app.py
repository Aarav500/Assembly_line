import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
import time
from flask import Flask, request, jsonify
from storage import Storage
from utils import now_ts, to_iso, random_secret

app = Flask(__name__)
storage = Storage()

# Background janitor to enforce planned revocations and cleanup
STOP_EVENT = threading.Event()

def janitor_loop(interval=1.0):
    while not STOP_EVENT.is_set():
        try:
            storage.enforce_planned_revocations()
            storage.cleanup_old_leases()
        except Exception:
            # Best-effort; avoid crashing background thread
            pass
        STOP_EVENT.wait(interval)

janitor_thread = threading.Thread(target=janitor_loop, daemon=True)
janitor_thread.start()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "time": to_iso(now_ts())})

@app.route('/secrets', methods=['POST'])
def create_secret():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name')
    if not name:
        return jsonify({"error": "name is required"}), 400

    value = data.get('value') or random_secret(32)
    ttl = int(data.get('ttl', 3600))
    max_ttl = int(data.get('max_ttl', 86400))

    if ttl <= 0 or max_ttl <= 0 or ttl > max_ttl:
        return jsonify({"error": "invalid ttl/max_ttl"}), 400

    secret, lease = storage.create_secret(name=name, value=value, ttl=ttl, max_ttl=max_ttl)

    return jsonify({
        "secret_id": secret.id,
        "name": secret.name,
        "version": secret.latest_version,
        "value": value,
        "lease": {
            "lease_id": lease.id,
            "ttl": lease.ttl,
            "max_ttl": lease.max_ttl,
            "created_at": to_iso(lease.created_at),
            "expires_at": to_iso(lease.created_at + lease.ttl)
        },
        "created_at": to_iso(secret.created_at)
    }), 201

@app.route('/secrets/<secret_id>', methods=['GET'])
def get_secret_metadata(secret_id):
    secret = storage.get_secret(secret_id)
    if not secret:
        return jsonify({"error": "not found"}), 404
    leases = storage.list_leases_by_secret(secret_id)
    by_version = {}
    for lease in leases:
        by_version.setdefault(str(lease.version), {"total": 0, "active": 0})
        by_version[str(lease.version)]["total"] += 1
        if lease.is_active(now_ts()):
            by_version[str(lease.version)]["active"] += 1
    return jsonify({
        "secret_id": secret.id,
        "name": secret.name,
        "versions": list(sorted(secret.versions.keys())),
        "latest_version": secret.latest_version,
        "leases": by_version,
        "created_at": to_iso(secret.created_at),
        "updated_at": to_iso(secret.updated_at)
    })

@app.route('/secrets/<secret_id>/value', methods=['GET'])
def get_secret_value(secret_id):
    lease_id = request.headers.get('X-Lease-Id')
    if not lease_id:
        return jsonify({"error": "X-Lease-Id header is required"}), 401
    version_param = request.args.get('version')
    lease = storage.get_lease(lease_id)
    if not lease:
        return jsonify({"error": "lease not found"}), 404
    if lease.secret_id != secret_id:
        return jsonify({"error": "lease does not belong to secret"}), 403
    if not lease.is_active(now_ts()):
        return jsonify({"error": "lease expired or revoked"}), 403

    if version_param is not None:
        try:
            requested_version = int(version_param)
        except ValueError:
            return jsonify({"error": "invalid version"}), 400
    else:
        requested_version = lease.version

    if requested_version != lease.version:
        return jsonify({"error": "lease not authorized for requested version"}), 403

    secret = storage.get_secret(secret_id)
    if not secret:
        return jsonify({"error": "secret not found"}), 404

    value = secret.versions.get(requested_version)
    if value is None:
        return jsonify({"error": "secret version not found"}), 404

    return jsonify({
        "secret_id": secret.id,
        "version": requested_version,
        "value": value
    })

@app.route('/secrets/<secret_id>/rotate', methods=['POST'])
def rotate_secret(secret_id):
    data = request.get_json(force=True, silent=True) or {}
    value = data.get('value') or random_secret(32)
    ttl = data.get('ttl')
    max_ttl = data.get('max_ttl')
    revoke_old_after_seconds = int(data.get('revoke_old_after_seconds', 0))

    if ttl is not None:
        ttl = int(ttl)
        if ttl <= 0:
            return jsonify({"error": "ttl must be > 0"}), 400
    if max_ttl is not None:
        max_ttl = int(max_ttl)
        if max_ttl <= 0:
            return jsonify({"error": "max_ttl must be > 0"}), 400
    if ttl is not None and max_ttl is not None and ttl > max_ttl:
        return jsonify({"error": "ttl cannot exceed max_ttl"}), 400

    try:
        secret, new_lease = storage.rotate_secret(
            secret_id=secret_id,
            value=value,
            ttl=ttl,
            max_ttl=max_ttl,
            revoke_old_after_seconds=revoke_old_after_seconds,
        )
    except KeyError:
        return jsonify({"error": "secret not found"}), 404

    return jsonify({
        "secret_id": secret.id,
        "new_version": secret.latest_version,
        "value": value,
        "lease": {
            "lease_id": new_lease.id,
            "ttl": new_lease.ttl,
            "max_ttl": new_lease.max_ttl,
            "created_at": to_iso(new_lease.created_at),
            "expires_at": to_iso(new_lease.created_at + new_lease.ttl)
        },
        "old_leases_revocation": {
            "scheduled": revoke_old_after_seconds > 0,
            "at": to_iso(now_ts() + revoke_old_after_seconds) if revoke_old_after_seconds > 0 else None
        }
    }), 200

@app.route('/leases/<lease_id>', methods=['GET'])
def get_lease(lease_id):
    lease = storage.get_lease(lease_id)
    if not lease:
        return jsonify({"error": "not found"}), 404
    status = 'active' if lease.is_active(now_ts()) else ('revoked' if lease.revoked_at else 'expired')
    return jsonify({
        "lease_id": lease.id,
        "secret_id": lease.secret_id,
        "version": lease.version,
        "status": status,
        "ttl": lease.ttl,
        "max_ttl": lease.max_ttl,
        "created_at": to_iso(lease.created_at),
        "expires_at": to_iso(lease.created_at + lease.ttl),
        "revoked_at": to_iso(lease.revoked_at) if lease.revoked_at else None
    })

@app.route('/leases/<lease_id>/renew', methods=['POST'])
def renew_lease(lease_id):
    data = request.get_json(force=True, silent=True) or {}
    additional_ttl = int(data.get('additional_ttl', 3600))
    if additional_ttl <= 0:
        return jsonify({"error": "additional_ttl must be > 0"}), 400

    try:
        lease = storage.renew_lease(lease_id, additional_ttl)
    except KeyError:
        return jsonify({"error": "lease not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "lease_id": lease.id,
        "ttl": lease.ttl,
        "max_ttl": lease.max_ttl,
        "created_at": to_iso(lease.created_at),
        "expires_at": to_iso(lease.created_at + lease.ttl)
    })

@app.route('/leases/<lease_id>/revoke', methods=['POST'])
def revoke_lease(lease_id):
    try:
        lease = storage.revoke_lease(lease_id)
    except KeyError:
        return jsonify({"error": "lease not found"}), 404
    return jsonify({
        "lease_id": lease.id,
        "revoked_at": to_iso(lease.revoked_at)
    })

@app.route('/secrets/<secret_id>/revoke_all', methods=['POST'])
def revoke_all(secret_id):
    version_param = request.args.get('version')
    version = None
    if version_param is not None:
        try:
            version = int(version_param)
        except ValueError:
            return jsonify({"error": "invalid version"}), 400
    try:
        count = storage.revoke_all_leases(secret_id, version)
    except KeyError:
        return jsonify({"error": "secret not found"}), 404
    return jsonify({"revoked": count})

@app.route('/secrets/<secret_id>', methods=['DELETE'])
def delete_secret(secret_id):
    try:
        storage.delete_secret(secret_id)
    except KeyError:
        return jsonify({"error": "not found"}), 404
    return jsonify({"deleted": True})

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    try:
        app.run(host='0.0.0.0', port=port)
    finally:
        STOP_EVENT.set()
        janitor_thread.join(timeout=2)



def create_app():
    return app
