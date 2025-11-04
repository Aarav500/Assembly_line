from flask import Blueprint, request, jsonify, current_app
from credential_manager import CredentialManager, CredentialError
from models import db, MachineCredential, CredentialVersion
from utils import require_api_key, audit_event

api_bp = Blueprint('api', __name__)


@api_bp.route('/credentials', methods=['POST'])
@require_api_key
def create_credential():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name')
    rotation_interval_seconds = data.get('rotation_interval_seconds')
    if not name:
        return jsonify({"error": "name is required"}), 400
    mgr = CredentialManager()
    try:
        cred, secret = mgr.create_credential(name=name, rotation_interval_seconds=rotation_interval_seconds)
    except CredentialError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({
        "id": cred.id,
        "name": cred.name,
        "access_key": cred.access_key,
        "secret": secret,
        "secret_version": 1,
        "status": cred.status,
        "rotation_interval_seconds": cred.rotation_interval_seconds,
        "created_at": cred.created_at.isoformat() + 'Z'
    }), 201


@api_bp.route('/credentials/<credential_id>', methods=['GET'])
@require_api_key
def get_credential(credential_id):
    try:
        cred = CredentialManager().get_credential(credential_id)
    except CredentialError as e:
        return jsonify({"error": str(e)}), 404

    versions = []
    for v in cred.versions:
        versions.append({
            "id": v.id,
            "version": v.version,
            "created_at": v.created_at.isoformat() + 'Z',
            "revoked_at": v.revoked_at.isoformat() + 'Z' if v.revoked_at else None,
            "reason": v.reason,
            "is_active": cred.active_version_id == v.id
        })

    return jsonify({
        "id": cred.id,
        "name": cred.name,
        "access_key": cred.access_key,
        "status": cred.status,
        "rotation_interval_seconds": cred.rotation_interval_seconds,
        "last_rotated_at": cred.last_rotated_at.isoformat() + 'Z' if cred.last_rotated_at else None,
        "compromised_at": cred.compromised_at.isoformat() + 'Z' if cred.compromised_at else None,
        "versions": versions,
    })


@api_bp.route('/credentials/<credential_id>/rotate', methods=['POST'])
@require_api_key
def rotate_credential(credential_id):
    reason = (request.get_json(silent=True) or {}).get('reason', 'manual-rotation')
    try:
        cred, secret = CredentialManager().rotate_credential(credential_id, reason=reason)
    except CredentialError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({
        "id": cred.id,
        "access_key": cred.access_key,
        "secret": secret,
        "secret_version": max(v.version for v in cred.versions),
        "status": cred.status
    })


@api_bp.route('/credentials/<credential_id>/revoke', methods=['POST'])
@require_api_key
def revoke_credential(credential_id):
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', 'manual-revoke')
    disable = bool(data.get('disable', False))
    try:
        cred = CredentialManager().revoke_current_version(credential_id, reason=reason, disable=disable)
    except CredentialError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({
        "id": cred.id,
        "status": cred.status,
        "active_version_id": cred.active_version_id
    })


@api_bp.route('/credentials/<credential_id>/breach', methods=['POST'])
@require_api_key
def breach_detected(credential_id):
    reason = (request.get_json(silent=True) or {}).get('reason', 'breach-detected')
    try:
        cred, secret = CredentialManager().breach_detected(credential_id, reason=reason)
    except CredentialError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({
        "id": cred.id,
        "access_key": cred.access_key,
        "secret": secret,
        "secret_version": max(v.version for v in cred.versions),
        "status": cred.status,
        "note": "rotated-after-breach"
    })


@api_bp.route('/validate', methods=['POST'])
def validate():
    data = request.get_json(force=True, silent=True) or {}
    access_key = data.get('access_key')
    secret = data.get('secret')
    if not access_key or not secret:
        return jsonify({"valid": False, "error": "access_key and secret required"}), 400
    valid, credential_id, status = CredentialManager().validate(access_key, secret)
    return jsonify({
        "valid": bool(valid),
        "credential_id": credential_id,
        "status": status
    })

