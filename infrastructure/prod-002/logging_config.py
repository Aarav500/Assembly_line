import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

from config import Config
from context import get_request_id, get_correlation_id
from utils.sanitization import sanitize_text, sanitize_exception_text


class JsonFormatter(logging.Formatter):
    def __init__(self, redacted_keys: list[str] | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redacted_keys = set([k.lower() for k in (redacted_keys or [])])

    def format(self, record: logging.LogRecord) -> str:
        # Base log structure
        log: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_text(str(record.getMessage())),
        }
        # Context
        rid = getattr(record, "request_id", None) or get_request_id()
        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        if rid:
            log["request_id"] = rid
        if cid:
            log["correlation_id"] = cid

        # Location
        log["module"] = record.module
        log["func"] = record.funcName
        log["line"] = record.lineno

        # Extra
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            for k, v in record.extra.items():
                log[k] = self._maybe_redact(k, v)

        # Exception
        if record.exc_info:
            log["exc"] = sanitize_exception_text(record.exc_info)

        return json.dumps(log, ensure_ascii=False)

    def _maybe_redact(self, key: str, value: Any) -> Any:
        if key and key.lower() in self.redacted_keys:
            return "[REDACTED]"
        if isinstance(value, str):
            return sanitize_text(value)
        if isinstance(value, dict):
            return {k: self._maybe_redact(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._maybe_redact("", v) for v in value]
        return value


def setup_logging(config: Config) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    root.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stdout)
    if config.LOG_JSON:
        formatter = JsonFormatter(redacted_keys=config.LOG_REDACT_FIELDS)
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Reduce noisy loggers if desired
    for noisy in ("werkzeug", "urllib3", "sentry_sdk"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

    logging.getLogger(__name__).debug("Logging configured", extra={"extra": {"level": config.LOG_LEVEL}})

