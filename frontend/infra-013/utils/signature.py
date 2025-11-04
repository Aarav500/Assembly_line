import hmac
import hashlib
import time
from typing import Optional


SIGNATURE_HEADER = "X-Signature"
TIMESTAMP_HEADER = "X-Timestamp"
SIGNATURE_SCHEME = "v1"


def _compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    payload = f"{timestamp}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_SCHEME}={digest}"


def verify_signature(headers, body: bytes, secret: str, tolerance_seconds: int) -> Optional[str]:
    """
    Verify HMAC-based signature provided in headers against the raw request body.
    Expected headers:
      - X-Timestamp: unix epoch seconds as string
      - X-Signature: "v1=<hex sha256 hmac>"

    Returns None on success; a string error message on failure.
    """
    sig_header = headers.get(SIGNATURE_HEADER)
    ts_header = headers.get(TIMESTAMP_HEADER)

    if not sig_header or not ts_header:
        return "missing signature or timestamp headers"

    try:
        ts = int(ts_header)
    except ValueError:
        return "invalid timestamp header"

    now = int(time.time())
    if abs(now - ts) > tolerance_seconds:
        return "timestamp outside tolerance"

    expected = _compute_signature(secret, ts_header, body)

    try:
        scheme, _ = sig_header.split("=", 1)
    except ValueError:
        return "invalid signature header format"

    if scheme != SIGNATURE_SCHEME:
        return "unsupported signature scheme"

    if not hmac.compare_digest(sig_header, expected):
        return "signature mismatch"

    return None


def generate_test_signature(secret: str, timestamp: int, body: bytes) -> str:
    return _compute_signature(secret, str(timestamp), body)

