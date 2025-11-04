import base64
import os
import logging
import threading
from functools import wraps
from datetime import datetime
from flask import request, current_app, jsonify
from cryptography.fernet import Fernet
from models import db, AuditEvent
import secrets
import time

_cipher = None
_cipher_lock = threading.Lock()


def get_cipher():
    global _cipher
    if _cipher is None:
        with _cipher_lock:
            if _cipher is None:
                key = current_app.config.get('ENCRYPTION_KEY')
                if isinstance(key, str):
                    key = key.encode('utf-8')
                # Validate size by attempting to create Fernet
                _cipher = Fernet(key)
    return _cipher


def encrypt_secret(plaintext: str) -> bytes:
    c = get_cipher()
    return c.encrypt(plaintext.encode('utf-8'))


def decrypt_secret(ciphertext: bytes) -> str:
    c = get_cipher()
    return c.decrypt(ciphertext).decode('utf-8')


def setup_audit_logger():
    log_path = current_app.config['AUDIT_LOG_FILE']
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger('audit')
    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def audit_event(event_type: str, message: str, credential_id: str = None, version_id: str = None):
    logger = setup_audit_logger()
    logger.info(f"{event_type} credential_id={credential_id} version_id={version_id} message={message}")
    ev = AuditEvent(event_type=event_type, credential_id=credential_id, version_id=version_id, message=message)
    db.session.add(ev)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected = current_app.config.get('ADMIN_API_KEY')
        if not expected or api_key != expected:
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


def generate_access_key(prefix: str = 'mch_') -> str:
    # 24-char random plus timestamp fragment for uniqueness
    rand = secrets.token_urlsafe(18).replace('-', '').replace('_', '')
    ts = format(int(time.time() * 1000), 'x')
    return f"{prefix}{ts}{rand}"

