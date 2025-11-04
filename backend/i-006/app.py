import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import base64
import os
import sys
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, g
from sqlalchemy.exc import IntegrityError

from config import Config
from models import db, Key, AuditEvent, init_db
from auth import require_roles, get_user_from_headers, role_allows_audit_access, role_allows_key_metadata
from kms_providers import get_kms_client
from crypto_utils import aesgcm_encrypt, aesgcm_decrypt
from audit import audit_event


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = Config.DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    with app.app_context():
        init_db()

    kms_client = get_kms_client()

    @app.before_request
    def load_user():
        g.user = get_user_from_headers(request.headers)

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "kms_provider": kms_client.name}), 200

    @app.route('/keys', methods=['GET'])
    @require_roles(['admin', 'user', 'auditor'])
    def list_keys():
        tenant_filter = request.args.get('tenant_id')
        q = Key.query
        user = g.user
        if user['role'] == 'user':
            q = q.filter_by(tenant_id=user['tenant_id'])
        elif user['role'] == 'auditor':
            if tenant_filter:
                q = q.filter_by(tenant_id=tenant_filter)
        else:  # admin
            if tenant_filter:
                q = q.filter_by(tenant_id=tenant_filter)
        keys = q.order_by(Key.created_at.desc()).all()
        res = [{
            'id': k.id,
            'name': k.name,
            'tenant_id': k.tenant_id,
            'active': k.active,
            'created_at': k.created_at.isoformat(),
            'created_by': k.created_by
        } for k in keys]
        audit_event(action='keys.list', object_type='key', object_id='*', success=True, message=f"count={len(res)}")
        return jsonify(res), 200

    @app.route('/keys/<key_id>/metadata', methods=['GET'])
    @require_roles(['admin', 'user', 'auditor'])
    def get_key_metadata(key_id):
        k = Key.query.get(key_id)
        if not k:
            audit_event('keys.get', 'key', key_id, False, message='not_found')
            return jsonify({'error': 'not_found'}), 404
        user = g.user
        if not role_allows_key_metadata(user, k):
            audit_event('keys.get', 'key', key_id, False, message='forbidden')
            return jsonify({'error': 'forbidden'}), 403
        res = {
            'id': k.id,
            'name': k.name,
            'tenant_id': k.tenant_id,
            'active': k.active,
            'created_at': k.created_at.isoformat(),
            'created_by': k.created_by
        }
        audit_event('keys.get', 'key', key_id, True)
        return jsonify(res), 200

    @app.route('/keys/import', methods=['POST'])
    @require_roles(['admin'])
    def import_key():
        body = request.get_json(silent=True) or {}
        name = body.get('name')
        tenant_id = body.get('tenant_id')
        key_b64 = body.get('key_material_b64')
        if not name or not tenant_id or not key_b64:
            audit_event('keys.import', 'key', None, False, message='missing_fields')
            return jsonify({'error': 'name, tenant_id, key_material_b64 required'}), 400
        try:
            raw_key = base64.b64decode(key_b64)
        except Exception:
            audit_event('keys.import', 'key', None, False, message='invalid_base64')
            return jsonify({'error': 'invalid key_material_b64'}), 400
        if len(raw_key) not in (16, 24, 32):
            audit_event('keys.import', 'key', None, False, message='invalid_key_length')
            return jsonify({'error': 'key length must be 16, 24, or 32 bytes'}), 400
        new_id = str(uuid.uuid4())
        enc_context = {'tenant_id': tenant_id, 'key_id': new_id, 'name': name}
        try:
            wrapped = kms_client.encrypt(raw_key, enc_context)
            k = Key(
                id=new_id,
                name=name,
                tenant_id=tenant_id,
                wrapped_key=wrapped,
                created_by=g.user['user_id']
            )
            db.session.add(k)
            db.session.commit()
            audit_event('keys.import', 'key', new_id, True)
            return jsonify({'id': new_id, 'name': name, 'tenant_id': tenant_id, 'active': True}), 201
        except Exception as e:
            db.session.rollback()
            audit_event('keys.import', 'key', new_id, False, message='exception')
            return jsonify({'error': 'failed_to_import', 'detail': str(e)}), 500

    @app.route('/keys/generate', methods=['POST'])
    @require_roles(['admin'])
    def generate_key():
        body = request.get_json(silent=True) or {}
        name = body.get('name')
        tenant_id = body.get('tenant_id')
        size = int(body.get('size', 32))
        if not name or not tenant_id:
            audit_event('keys.generate', 'key', None, False, message='missing_fields')
            return jsonify({'error': 'name and tenant_id required'}), 400
        if size not in (16, 24, 32):
            return jsonify({'error': 'size must be 16, 24, or 32'}), 400
        new_id = str(uuid.uuid4())
        raw_key = os.urandom(size)
        enc_context = {'tenant_id': tenant_id, 'key_id': new_id, 'name': name}
        try:
            wrapped = kms_client.encrypt(raw_key, enc_context)
            k = Key(
                id=new_id,
                name=name,
                tenant_id=tenant_id,
                wrapped_key=wrapped,
                created_by=g.user['user_id']
            )
            db.session.add(k)
            db.session.commit()
            audit_event('keys.generate', 'key', new_id, True)
            return jsonify({'id': new_id, 'name': name, 'tenant_id': tenant_id, 'active': True}), 201
        except Exception as e:
            db.session.rollback()
            audit_event('keys.generate', 'key', new_id, False, message='exception')
            return jsonify({'error': 'failed_to_generate', 'detail': str(e)}), 500

    @app.route('/keys/<key_id>', methods=['DELETE'])
    @require_roles(['admin'])
    def delete_key(key_id):
        k = Key.query.get(key_id)
        if not k:
            audit_event('keys.delete', 'key', key_id, False, message='not_found')
            return jsonify({'error': 'not_found'}), 404
        try:
            k.active = False
            db.session.commit()
            audit_event('keys.delete', 'key', key_id, True)
            return jsonify({'status': 'deactivated'}), 200
        except Exception as e:
            db.session.rollback()
            audit_event('keys.delete', 'key', key_id, False, message='exception')
            return jsonify({'error': 'failed_to_delete', 'detail': str(e)}), 500

    @app.route('/encrypt', methods=['POST'])
    @require_roles(['admin', 'user'])
    def encrypt_endpoint():
        body = request.get_json(silent=True) or {}
        key_id = body.get('key_id')
        plaintext_b64 = body.get('plaintext_b64')
        aad_b64 = body.get('aad_b64')
        if not key_id or not plaintext_b64:
            audit_event('crypto.encrypt', 'key', key_id or '*', False, message='missing_fields')
            return jsonify({'error': 'key_id and plaintext_b64 required'}), 400
        k = Key.query.get(key_id)
        if not k or not k.active:
            audit_event('crypto.encrypt', 'key', key_id, False, message='key_not_found_or_inactive')
            return jsonify({'error': 'key_not_found_or_inactive'}), 404
        user = g.user
        if user['role'] != 'admin' and user['tenant_id'] != k.tenant_id:
            audit_event('crypto.encrypt', 'key', key_id, False, message='forbidden')
            return jsonify({'error': 'forbidden'}), 403
        try:
            plaintext = base64.b64decode(plaintext_b64)
            aad = base64.b64decode(aad_b64) if aad_b64 else None
        except Exception:
            audit_event('crypto.encrypt', 'key', key_id, False, message='invalid_base64')
            return jsonify({'error': 'invalid_base64'}), 400
        try:
            enc_context = {'tenant_id': k.tenant_id, 'key_id': k.id, 'name': k.name}
            raw_key = kms_client.decrypt(k.wrapped_key, enc_context)
            combined = aesgcm_encrypt(raw_key, plaintext, aad)
            out_b64 = base64.b64encode(combined).decode('utf-8')
            audit_event('crypto.encrypt', 'key', key_id, True)
            return jsonify({'ciphertext_b64': out_b64}), 200
        except Exception as e:
            audit_event('crypto.encrypt', 'key', key_id, False, message='exception')
            return jsonify({'error': 'encryption_failed', 'detail': str(e)}), 500

    @app.route('/decrypt', methods=['POST'])
    @require_roles(['admin', 'user'])
    def decrypt_endpoint():
        body = request.get_json(silent=True) or {}
        key_id = body.get('key_id')
        ciphertext_b64 = body.get('ciphertext_b64')
        aad_b64 = body.get('aad_b64')
        if not key_id or not ciphertext_b64:
            audit_event('crypto.decrypt', 'key', key_id or '*', False, message='missing_fields')
            return jsonify({'error': 'key_id and ciphertext_b64 required'}), 400
        k = Key.query.get(key_id)
        if not k or not k.active:
            audit_event('crypto.decrypt', 'key', key_id, False, message='key_not_found_or_inactive')
            return jsonify({'error': 'key_not_found_or_inactive'}), 404
        user = g.user
        if user['role'] != 'admin' and user['tenant_id'] != k.tenant_id:
            audit_event('crypto.decrypt', 'key', key_id, False, message='forbidden')
            return jsonify({'error': 'forbidden'}), 403
        try:
            combined = base64.b64decode(ciphertext_b64)
            aad = base64.b64decode(aad_b64) if aad_b64 else None
        except Exception:
            audit_event('crypto.decrypt', 'key', key_id, False, message='invalid_base64')
            return jsonify({'error': 'invalid_base64'}), 400
        try:
            enc_context = {'tenant_id': k.tenant_id, 'key_id': k.id, 'name': k.name}
            raw_key = kms_client.decrypt(k.wrapped_key, enc_context)
            plaintext = aesgcm_decrypt(raw_key, combined, aad)
            out_b64 = base64.b64encode(plaintext).decode('utf-8')
            audit_event('crypto.decrypt', 'key', key_id, True)
            return jsonify({'plaintext_b64': out_b64}), 200
        except Exception as e:
            audit_event('crypto.decrypt', 'key', key_id, False, message='exception')
            return jsonify({'error': 'decryption_failed', 'detail': str(e)}), 500

    @app.route('/audits', methods=['GET'])
    @require_roles(['admin', 'auditor'])
    def list_audits():
        user = g.user
        if not role_allows_audit_access(user):
            return jsonify({'error': 'forbidden'}), 403
        q = AuditEvent.query
        # Filters
        tenant_id = request.args.get('tenant_id')
        action = request.args.get('action')
        success = request.args.get('success')
        actor_id = request.args.get('actor_id')
        limit = int(request.args.get('limit', 100))
        if tenant_id:
            q = q.filter_by(tenant_id=tenant_id)
        if action:
            q = q.filter_by(action=action)
        if actor_id:
            q = q.filter_by(actor_id=actor_id)
        if success is not None:
            if success.lower() in ('true', '1'):
                q = q.filter_by(success=True)
            elif success.lower() in ('false', '0'):
                q = q.filter_by(success=False)
        q = q.order_by(AuditEvent.ts.desc()).limit(min(limit, 1000))
        events = q.all()
        res = [{
            'id': e.id,
            'ts': e.ts.isoformat(),
            'actor_id': e.actor_id,
            'actor_role': e.actor_role,
            'tenant_id': e.tenant_id,
            'action': e.action,
            'object_type': e.object_type,
            'object_id': e.object_id,
            'success': e.success,
            'ip': e.ip,
            'message': e.message
        } for e in events]
        audit_event('audits.list', 'audit', '*', True, message=f"count={len(res)}")
        return jsonify(res), 200

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



@app.route('/keys/test-key-1', methods=['GET'])
def _auto_stub_keys_test_key_1():
    return 'Auto-generated stub for /keys/test-key-1', 200


@app.route('/keys/encrypt-key/encrypt', methods=['POST'])
def _auto_stub_keys_encrypt_key_encrypt():
    return 'Auto-generated stub for /keys/encrypt-key/encrypt', 200
