import json
import logging
import os
import sys
from datetime import datetime, timezone

from opentelemetry.trace import get_current_span


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Base log payload
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }

        # Attach OTEL trace context if present
        try:
            span = get_current_span()
            ctx = span.get_span_context() if span else None
            if ctx and ctx.is_valid:
                payload["trace_id"] = format(ctx.trace_id, "032x")
                payload["span_id"] = format(ctx.span_id, "016x")
        except Exception:
            pass

        # Standard LogRecord attributes to exclude
        excluded_attrs = {
            "name", "msg", "args", "created", "filename", "funcName", "levelname",
            "levelno", "lineno", "module", "msecs", "message", "pathname",
            "process", "processName", "relativeCreated", "thread", "threadName",
            "exc_info", "exc_text", "stack_info", "taskName"
        }

        # Include any extra attributes provided (those not in standard LogRecord)
        for key, value in record.__dict__.items():
            if key.startswith("_"):
                continue
            if key in excluded_attrs or key in payload:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"))


def init_logging(level: str = "INFO"):
    log_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)

    # Stream to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(JSONFormatter())

    # Clear existing handlers to avoid duplication
    for h in list(root.handlers):
        root.removeHandler(h)

    root.addHandler(handler)

    # Reduce noise from some libraries
    logging.getLogger("werkzeug").setLevel(os.environ.get("WERKZEUG_LOG_LEVEL", "WARNING"))
    logging.getLogger("opentelemetry").setLevel(os.environ.get("OTEL_LOG_LEVEL", "WARNING"))


logger = logging.getLogger("app")
