import base64
import json
import os
from typing import Dict, Any

from cryptography.fernet import Fernet, InvalidToken


def require_env_secrets():
    required = ['ENCRYPTION_KEY', 'ACCESS_TOKEN_SECRET']
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required secrets: {', '.join(missing)}")


def get_fernet() -> Fernet:
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        raise RuntimeError('ENCRYPTION_KEY not set')
    return Fernet(key)


def encrypt_json(data: Dict[str, Any]) -> str:
    f = get_fernet()
    b = json.dumps(data, separators=(',', ':')).encode('utf-8')
    token = f.encrypt(b)
    return base64.urlsafe_b64encode(token).decode('ascii')


def decrypt_json(token_b64: str) -> Dict[str, Any]:
    f = get_fernet()
    raw = base64.urlsafe_b64decode(token_b64.encode('ascii'))
    try:
        dec = f.decrypt(raw)
    except InvalidToken:
        raise ValueError('Decryption failed')
    return json.loads(dec.decode('utf-8'))


def encrypt_email(email: str) -> str:
    return encrypt_json({'email': email})


def decrypt_email(enc: str) -> str:
    data = decrypt_json(enc)
    return data.get('email', '')\

