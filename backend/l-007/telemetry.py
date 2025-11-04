import os
import logging
import json
from datetime import datetime
from typing import Optional

from flask import Flask
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

try:
    # Prefer HTTP OTLP exporter (works with OTEL collector at http://host:4318)
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as OTLPHTTPSpanExporter,
    )
except Exception:  # pragma: no cover - fallback if http exporter not available
    OTLPHTTPSpanExporter = None  # type: ignore


class JsonOTLPLikeFormatter(logging.Formatter):
    def __init__(self, service_name: str, environment: str):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        try:
            span = trace.get_current_span()
            ctx = span.get_span_context() if span else None
            trace_id = (
                format(ctx.trace_id, "032x") if ctx and ctx.is_valid else ""
            )
            span_id = (
                format(ctx.span_id, "016x") if ctx and ctx.is_valid else ""
            )
        except Exception:
            trace_id = ""
            span_id = ""

        payload = {
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id,
            "span_id": span_id,
            "service.name": self.service_name,
            "deployment.environment": self.environment,
            "module": record.module,
            "filename": record.filename,
            "lineno": record.lineno,
        }

        if record.exc_info:
            try:
                payload["exc_info"] = self.formatException(record.exc_info)
            except Exception:
                payload["exc_info"] = "<unavailable>"

        # Include extras if present
        for key in ("work_n", "duration_sec", "total"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        return json.dumps(payload, ensure_ascii=False)


def _build_resource(service_name: str, service_version: str, environment: str) -> Resource:
    return Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: service_version,
            "deployment.environment": environment,
        }
    )


def _setup_logging(service_name: str, environment: str) -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Ensure basic, structured logging to stdout
    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove pre-existing handlers to avoid duplicate logs
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(JsonOTLPLikeFormatter(service_name, environment))
    root.addHandler(handler)

    # Include trace/span correlation on Python logging records
    LoggingInstrumentor().instrument(set_logging_format=False)


def _setup_tracing(service_name: str, service_version: str, environment: str) -> None:
    resource = _build_resource(service_name, service_version, environment)
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter if endpoint provided, else console exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    use_console = os.getenv("TRACES_CONSOLE_EXPORT", "").strip().lower() in ("1", "true", "yes")

    if otlp_endpoint and OTLPHTTPSpanExporter is not None:
        # Accept either base endpoint (http://host:4318) or full path
        if "/v1/traces" not in otlp_endpoint:
            otlp_endpoint = otlp_endpoint.rstrip("/") + "/v1/traces"
        otlp_exporter = OTLPHTTPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    if not otlp_endpoint or use_console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)


def init_telemetry(app: Optional[Flask] = None) -> None:
    service_name = os.getenv("SERVICE_NAME", "flask-telemetry-service")
    service_version = os.getenv("SERVICE_VERSION", "0.1.0")
    environment = os.getenv("ENVIRONMENT", "dev")

    _setup_logging(service_name, environment)
    _setup_tracing(service_name, service_version, environment)

    # Auto-instrument Flask and outbound HTTP calls
    if app is not None:
        FlaskInstrumentor().instrument_app(app)
    else:
        FlaskInstrumentor().instrument()
    RequestsInstrumentor().instrument()

