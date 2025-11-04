import hashlib
from typing import Any, Dict


def stable_bucket(*parts: str) -> float:
    """Generate a deterministic bucket in [0, 1) from input parts.
    Uses SHA-256 for stability and uniformity.
    """
    joined = "|".join(parts)
    h = hashlib.sha256(joined.encode("utf-8")).digest()
    # Use first 8 bytes (64 bits) for a large integer, map to [0, 1)
    n = int.from_bytes(h[:8], byteorder="big", signed=False)
    return (n / float(2 ** 64))


def validate_percentage(value: float) -> float:
    if value < 0 or value > 100:
        raise ValueError("Percentage must be between 0 and 100")
    return float(value)


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "t", "yes", "y", "on"):  # noqa
            return True
        if v in ("0", "false", "f", "no", "n", "off"):  # noqa
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def now_iso() -> str:
    # Keep it simple: naive UTC string
    import datetime as _dt
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def error_response(message: str, status: int = 400, extra: Dict[str, Any] | None = None) -> (Dict[str, Any], int):
    payload = {"error": message}
    if extra:
        payload.update(extra)
    return payload, status

