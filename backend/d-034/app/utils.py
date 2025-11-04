import hashlib
import os
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional
from flask import current_app, request, jsonify
from dateutil import parser, tz


def ensure_instance_dir() -> None:
    inst_dir = os.path.join(os.getcwd(), 'instance')
    try:
        os.makedirs(inst_dir, exist_ok=True)
    except Exception:
        pass


def parse_iso_datetime_utc_naive(value: str) -> datetime:
    if not value:
        raise ValueError('datetime string required')
    dt = parser.isoparse(value)
    if dt.tzinfo is None:
        # assume UTC if no timezone provided
        dt = dt.replace(tzinfo=tz.UTC)
    dt_utc = dt.astimezone(tz.UTC).replace(tzinfo=None)
    return dt_utc


def isoformat_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    # Assume naive dt is UTC
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz.UTC).replace(tzinfo=None)
    return dt.isoformat(timespec='seconds') + 'Z'


def get_auth_token_from_request() -> Optional[str]:
    # Support Authorization: Bearer <token> or ?token=
    auth = request.headers.get('Authorization', '')
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1]
    token = request.args.get('token') or (request.get_json(silent=True) or {}).get('token')
    return token


def require_auth(fn: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        token = get_auth_token_from_request()
        expected = current_app.config.get('AUTH_TOKEN')
        if not expected:
            return jsonify({'error': 'server not configured with AUTH_TOKEN'}), 500
        if not token or token != expected:
            return jsonify({'error': 'unauthorized'}), 401
        return fn(*args, **kwargs)
    return wrapper


def stable_percentage(key: str) -> int:
    # Deterministic 0..99 bucket
    h = hashlib.sha256(key.encode('utf-8')).hexdigest()
    # Use first 8 hex chars -> 32 bits
    val = int(h[:8], 16)
    return val % 100

