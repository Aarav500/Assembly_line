import json
import logging
import os
import sys
from datetime import datetime, timezone

from opentelemetry import trace

try:
    from pythonjsonlogger import jsonlogger
except Exception:  # noqa: S110
    jsonlogger = None

_LOGGING_CONFIGURED = False


class OTELCorrelationFilter(logging.Filter):
    def filter(self, record):  # noqa: D401
        span = trace.get_current_span()
        ctx = getattr(span, "get_span_context", lambda: None)()
        if ctx and getattr(ctx, "is_valid", False):
            # Hex-encoded IDs
            record.trace_id = f"{ctx.trace_id:032x}"
            record.span_id = f"{ctx.span_id:016x}"
            record.trace_flags = int(getattr(ctx, "trace_flags", 0))
        else:
            record.trace_id = None
            record.span_id = None
            record.trace_flags = None
        record.service_name = (
            os.environ.get("OTEL_SERVICE_NAME")
            or os.environ.get("SERVICE_NAME")
            or "flask-app"
        )
        return True


class RFC3339TimeJSONFormatter(jsonlogger.JsonFormatter):
    def formatTime(self, record, datefmt=None):  # noqa: N802
        # RFC3339 / ISO8601 with Zulu
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")


def setup_logging():
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED and os.environ.get("INSTRUMENTATION_FORCE_LOG_CONFIG", "0") not in ("1", "true", "True"):
        return

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    try:
        numeric_level = getattr(logging, level)
    except AttributeError:
        numeric_level = logging.INFO

    root = logging.getLogger()

    # Clear existing handlers if forcing
    if os.environ.get("INSTRUMENTATION_FORCE_LOG_CONFIG", "0") in ("1", "true", "True"):
        for h in list(root.handlers):
            root.removeHandler(h)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(OTELCorrelationFilter())

        log_format = os.environ.get("LOG_FORMAT", "json").lower()
        if log_format == "json" and jsonlogger is not None:
            fmt = RFC3339TimeJSONFormatter(
                fmt=(
                    "%(asctime)s %(levelname)s %(name)s %(message)s "
                    "trace_id=%(trace_id)s span_id=%(span_id)s service_name=%(service_name)s"
                )
            )
            handler.setFormatter(fmt)
        else:
            formatter = logging.Formatter(
                fmt=(
                    "%(asctime)s %(levelname)s %(name)s %(message)s "
                    "trace_id=%(trace_id)s span_id=%(span_id)s service_name=%(service_name)s"
                )
            )
            handler.setFormatter(formatter)

        root.addHandler(handler)
        root.setLevel(numeric_level)

    # Reduce verbosity of noisy loggers if desired
    for noisy in ["werkzeug", "opentelemetry.sdk.metrics", "opentelemetry.sdk.trace"]:
        logging.getLogger(noisy).setLevel(os.environ.get("NOISY_LOG_LEVEL", "WARNING").upper())

    _LOGGING_CONFIGURED = True

