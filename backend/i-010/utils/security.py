import hmac
import hashlib
import functools
from flask import current_app, request, jsonify


def verify_hmac_signature(secret: bytes, body: bytes, signature_header: str | None) -> bool:
    if not signature_header:
        return False
    sig = signature_header.strip()
    if sig.startswith('sha256='):
        sig = sig.split('=', 1)[1]
    mac = hmac.new(secret, body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(mac, sig)
    except Exception:
        return False


def require_api_key(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        required = current_app.config.get('API_KEY')
        if required:
            provided = request.headers.get('X-API-Key')
            if not provided or not hmac.compare_digest(provided, required):
                return jsonify({'error': 'unauthorized'}), 401
        return fn(*args, **kwargs)
    return wrapper

