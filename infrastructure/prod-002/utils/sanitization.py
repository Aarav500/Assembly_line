import re
import traceback
from typing import Any, Dict, Iterable, Tuple

from config import Config


# Simple regex for common secret patterns and emails
_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)bearer\s+[a-z0-9\-\._~\+\/]+=*"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*([a-z0-9\-]{10,})"),
    re.compile(r"(?i)token\s*[:=]\s*([a-z0-9\-\._~\+\/]{8,})"),
]
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def sanitize_text(value: str) -> str:
    if not value:
        return value
    # Redact known secret patterns
    s = value
    for pat in _SECRET_PATTERNS:
        s = pat.sub("[REDACTED]", s)
    s = _EMAIL_RE.sub("[REDACTED_EMAIL]", s)
    return s


def sanitize_exception_text(exc_info_or_exc) -> str:
    # Accept Exception or exc_info tuple
    if isinstance(exc_info_or_exc, BaseException):
        te = traceback.TracebackException.from_exception(exc_info_or_exc, capture_locals=False)
        stack = "".join(te.format())
    elif isinstance(exc_info_or_exc, tuple):
        stack = "".join(traceback.format_exception(*exc_info_or_exc))
    else:
        stack = str(exc_info_or_exc)

    # Limit stack size
    lines = stack.splitlines()
    max_frames = Config().MAX_STACK_FRAMES
    if len(lines) > max_frames:
        lines = lines[:max_frames] + ["... [truncated] ..."]

    return sanitize_text("\n".join(lines))


def _redact_dict(d: Dict[str, Any], redacted_keys: Iterable[str]) -> Dict[str, Any]:
    redacted = {}
    lower_keys = set(k.lower() for k in redacted_keys)
    for k, v in d.items():
        if k.lower() in lower_keys:
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = _redact_dict(v, redacted_keys)
        elif isinstance(v, list):
            redacted[k] = [_redact_dict(x, redacted_keys) if isinstance(x, dict) else (sanitize_text(x) if isinstance(x, str) else x) for x in v]
        elif isinstance(v, str):
            redacted[k] = sanitize_text(v)
        else:
            redacted[k] = v
    return redacted


def sanitize_sentry_event(event: Dict[str, Any], hint: Dict[str, Any] | None, redacted_keys: Iterable[str]) -> Dict[str, Any] | None:
    # Drop breadcrumbs payloads which may include headers
    if "breadcrumbs" in event:
        b = event.get("breadcrumbs", {})
        if isinstance(b, dict) and "values" in b:
            for crumb in b.get("values", []) or []:
                if isinstance(crumb, dict) and "data" in crumb:
                    crumb["data"] = {}  # drop data in breadcrumbs

    # Redact request context
    req = event.get("request")
    if isinstance(req, dict):
        for k in ("headers", "cookies", "data", "env"):  # remove sensitive
            if k in req:
                req[k] = {}
        if "url" in req:
            req["url"] = sanitize_text(req["url"])[:512]
        if "query_string" in req and isinstance(req["query_string"], str):
            req["query_string"] = sanitize_text(req["query_string"])[:512]

    # Redact tags and extra
    if "tags" in event and isinstance(event["tags"], dict):
        event["tags"] = _redact_dict(event["tags"], redacted_keys)
    if "extra" in event and isinstance(event["extra"], dict):
        event["extra"] = _redact_dict(event["extra"], redacted_keys)

    # Sanitize exception values
    ex = event.get("exception")
    if isinstance(ex, dict) and "values" in ex:
        for val in ex.get("values", []) or []:
            if isinstance(val, dict) and "value" in val and isinstance(val["value"], str):
                val["value"] = sanitize_text(val["value"])[:512]

    return event

