from datetime import datetime
from flask import request
from typing import Optional

def dt_to_iso(dt: datetime) -> str:
    # Always format with microseconds and Z suffix
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def parse_iso_datetime(s: str) -> Optional[datetime]:
    if not s:
        return None
    # Support with/without microseconds, and trailing Z
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1]
    fmts = [
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d'
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError('Invalid datetime format, expected ISO8601')


def get_client_ip() -> str:
    # Prefer X-Forwarded-For if present
    xff = request.headers.get('X-Forwarded-For')
    if xff:
        # may contain multiple IPs
        return xff.split(',')[0].strip()
    return request.remote_addr or ''


def get_user_agent() -> str:
    return request.headers.get('User-Agent', '')[:256]


def get_request_user_id() -> Optional[str]:
    return request.headers.get('X-User-Id') or request.headers.get('X-User-ID')

