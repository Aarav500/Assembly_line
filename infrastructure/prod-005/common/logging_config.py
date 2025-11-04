import json
import logging
import os
import sys
from datetime import datetime

from pythonjsonlogger import jsonlogger
from flask import has_request_context, request

from .tracing import get_request_id, get_trace_id, get_span_id


class RequestContextFilter(logging.Filter):
    def __init__(self, service_name: str = None):
        super().__init__()
        self.service_name = service_name or os.getenv("SERVICE_NAME", "unknown-service")

    def filter(self, record: logging.LogRecord) -> bool:
        # Base context
        record.service = self.service_name
        record.request_id = get_request_id("-")
        record.trace_id = get_trace_id("-")
        record.span_id = get_span_id("-")

        # HTTP request info when available
        if has_request_context():
            try:
                record.method = request.method
                record.path = request.path
                record.remote_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
            except Exception:
                record.method = None
                record.path = None
                record.remote_addr = None
        else:
            record.method = None
            record.path = None
            record.remote_addr = None
        return True


def _build_formatter() -> logging.Formatter:
    fmt = jsonlogger.JsonFormatter(
        fmt="%(timestamp)s %(level)s %(name)s %(message)s",
        json_default=str,
    )

    # Monkey patch to inject timestamp consistently
    def add_fields(self, log_record, record, message_dict):
        super(self.__class__, self).add_fields(log_record, record, message_dict)  # type: ignore
        # Standardize keys
        log_record["timestamp"] = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        # Bring in extras if present
        for key in (
            "service",
            "request_id",
            "trace_id",
            "span_id",
            "method",
            "path",
            "remote_addr",
        ):
            val = getattr(record, key, None)
            if val is not None:
                log_record[key] = val

    # bind patched method
    fmt.add_fields = add_fields.__get__(fmt, fmt.__class__)  # type: ignore
    return fmt


def setup_logging(service_name: str = None, level: str = None) -> None:
    # Determine log level
    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    try:
        log_level = getattr(logging, level_name)
    except AttributeError:
        log_level = logging.INFO

    root = logging.getLogger()
    # avoid duplicate handlers if called twice
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(_build_formatter())
    handler.addFilter(RequestContextFilter(service_name))

    root.setLevel(log_level)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

