import os
from datetime import datetime, timedelta
from typing import Any, Dict

from flask import Blueprint, jsonify, request, current_app, abort

from models import db, Submission, ConsentPolicy, ContactEmail, AuditEvent
from privacy import minimize_payload, PURPOSE_RULES, submission_token, verify_submission_token
from security import encrypt_json, decrypt_json, encrypt_email, decrypt_email

privacy_bp = Blueprint('privacy', __name__)


def _current_policy() -> ConsentPolicy:
    return ConsentPolicy.query.order_by(ConsentPolicy.version.desc()).first()


def _retention_deadline() -> datetime:
    days = current_app.config.get('DATA_RETENTION_DAYS', 30)
    return datetime.utcnow() + timedelta(days=days)


@privacy_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200


@privacy_bp.route('/privacy-policy', methods=['GET'])
def privacy_policy():
    p = _current_policy()
    return jsonify({'version': p.version, 'text': p.text, 'effective_at': p.effective_at.isoformat() + 'Z'})


@privacy_bp.route('/submit', methods=['POST'])
def submit():
    # Do not log request body. Flask default logger is quiet; ensure any upstream avoids body logging.
    if not request.is_json:
        return jsonify({'error': 'JSON required'}), 400

    body = request.get_json(silent=True) or {}
    purpose = body.get('purpose')
    consent = body.get('consent') or {}

    if not purpose:
        return jsonify({'error': 'purpose required'}), 400

    if purpose not in PURPOSE_RULES:
        return jsonify({'error': 'unsupported purpose'}), 400

    policy = _current_policy()
    if not consent or consent.get('accept') is not True or consent.get('version') != policy.version:
        return jsonify({'error': 'valid consent required for stated purpose'}), 400

    # Minimize payload
    minimized = minimize_payload(body, purpose)

    # Separate email if allowed, never store in main payload
    email_enc = None
    if 'email' in minimized:
        email_val = minimized.pop('email')
        if isinstance(email_val, str) and email_val:
            email_enc = encrypt_email(email_val)

    # Encrypt minimized payload
    encrypted_payload = encrypt_json(minimized)

    # Create submission with TTL
    submission = Submission(
        purpose=purpose,
        payload_encrypted=encrypted_payload,
        consent_version=policy.version,
        expires_at=_retention_deadline(),
    )
    db.session.add(submission)
    db.session.flush()

    if email_enc:
        db.session.add(ContactEmail(submission_id=submission.id, email_encrypted=email_enc))

    db.session.add(AuditEvent(submission_id=submission.id, event_type='created'))
    db.session.commit()

    access = submission_token(submission.id)
    return jsonify({
        'id': submission.id,
        'access_token': access,
        'purpose': purpose,
        'expires_at': submission.expires_at.isoformat() + 'Z',
        'consent_version': submission.consent_version,
        'note': 'Store the access_token securely; it is required to view, export, or delete this submission.'
    }), 201


def _auth_submission(submission_id: str) -> Submission:
    token = request.headers.get('X-Submission-Token') or request.args.get('access_token')
    if not token or not verify_submission_token(submission_id, token):
        abort(403)
    sub = Submission.query.get_or_404(submission_id)
    return sub


@privacy_bp.route('/submission/<submission_id>', methods=['GET'])
def get_submission(submission_id: str):
    sub = _auth_submission(submission_id)
    data = decrypt_json(sub.payload_encrypted)
    # Do not return email by default
    return jsonify({
        'id': sub.id,
        'purpose': sub.purpose,
        'data': data,
        'created_at': sub.created_at.isoformat() + 'Z',
        'expires_at': sub.expires_at.isoformat() + 'Z',
        'consent_version': sub.consent_version,
    })


@privacy_bp.route('/submission/<submission_id>/export', methods=['GET'])
def export_submission(submission_id: str):
    sub = _auth_submission(submission_id)
    data = decrypt_json(sub.payload_encrypted)
    email_row = ContactEmail.query.filter_by(submission_id=sub.id).first()
    email_val = decrypt_email(email_row.email_encrypted) if email_row else None
    export = {
        'id': sub.id,
        'purpose': sub.purpose,
        'data': data,
        'email': email_val,
        'created_at': sub.created_at.isoformat() + 'Z',
        'expires_at': sub.expires_at.isoformat() + 'Z',
        'consent_version': sub.consent_version,
        'policy_version': sub.consent_version,
    }
    return jsonify(export)


@privacy_bp.route('/submission/<submission_id>', methods=['DELETE'])
def delete_submission(submission_id: str):
    sub = _auth_submission(submission_id)
    db.session.add(AuditEvent(submission_id=sub.id, event_type='deleted'))
    db.session.delete(sub)
    db.session.commit()
    return jsonify({'status': 'deleted', 'id': submission_id})


@privacy_bp.route('/admin/data-inventory', methods=['GET'])
def data_inventory():
    _require_admin()
    # Describe minimal schema and retention policy
    inventory = {
        'retention_days': current_app.config.get('DATA_RETENTION_DAYS', 30),
        'entities': [
            {
                'name': 'Submission',
                'fields': ['id', 'purpose', 'payload_encrypted', 'consent_version', 'created_at', 'expires_at'],
                'notes': 'payload_encrypted holds minimized JSON encrypted at rest. No IP/user-agent stored.'
            },
            {
                'name': 'ContactEmail',
                'fields': ['id', 'submission_id', 'email_encrypted'],
                'notes': 'Email stored only when allowed and necessary, encrypted separately.'
            },
            {
                'name': 'ConsentPolicy',
                'fields': ['id', 'version', 'text', 'effective_at'],
                'notes': 'Versioned consent policy for transparency.'
            },
            {
                'name': 'AuditEvent',
                'fields': ['id', 'submission_id', 'event_type', 'created_at'],
                'notes': 'Minimal audit data; no PII.'
            }
        ],
        'purposes': PURPOSE_RULES,
    }
    return jsonify(inventory)


@privacy_bp.route('/admin/policies', methods=['POST'])
def create_policy():
    _require_admin()
    body = request.get_json(silent=True) or {}
    text = body.get('text')
    version = body.get('version')
    if not isinstance(version, int) or not text:
        return jsonify({'error': 'version (int) and text required'}), 400
    if ConsentPolicy.query.filter_by(version=version).first():
        return jsonify({'error': 'version already exists'}), 400
    p = ConsentPolicy(version=version, text=text)
    db.session.add(p)
    db.session.commit()
    return jsonify({'status': 'created', 'version': version}), 201


@privacy_bp.route('/admin/retention/sweep', methods=['POST'])
def retention_sweep():
    _require_admin()
    from privacy import run_retention_once
    run_retention_once()
    return jsonify({'status': 'ok'})


def _require_admin():
    provided = request.headers.get('X-Admin-Key')
    expected = current_app.config.get('ADMIN_API_KEY')
    if not expected or provided != expected:
        abort(403)\

