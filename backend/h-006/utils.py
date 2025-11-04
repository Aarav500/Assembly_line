from datetime import datetime, timezone


def _ensure_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # Treat naive as UTC already
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def parse_iso8601(ts: str) -> datetime:
    # Accepts ISO 8601 like 2024-01-01T12:34:56Z or with offset
    s = ts.strip()
    # Python's fromisoformat does not accept Z, replace with +00:00
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"Invalid ISO 8601 timestamp: {ts}") from e
    return _ensure_naive_utc(dt)


def parse_as_of_param(param: str) -> datetime:
    if param is None or param == "":
        return utc_now_naive()
    if param.lower() in ("now", "latest"):
        return utc_now_naive()
    return parse_iso8601(param)


def utc_now_naive() -> datetime:
    # Naive UTC datetime
    return datetime.utcnow()


def to_iso8601(dt: datetime) -> str:
    # Return ISO 8601 with Z
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # Use timespec=seconds for brevity
    return dt.isoformat().replace("+00:00", "Z")

