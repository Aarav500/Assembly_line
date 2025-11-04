import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPSpanExporterGRPC
    _HAS_OTLP = True
except Exception:  # pragma: no cover
    _HAS_OTLP = False
    OTLPSpanExporterGRPC = None  # type: ignore


def setup_tracing(service_name: str, flask_app: Optional[object] = None):
    """
    Configure OpenTelemetry tracing with either OTLP (if enabled) or Console exporter.
    Also instruments Flask, Requests, and Redis.
    """
    # Avoid duplicate initialization in some environments
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        # If already a TracerProvider, assume initialized
        pass

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = None
    use_otlp = os.getenv("TRACE_EXPORTER", "console").lower() == "otlp" or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if use_otlp and _HAS_OTLP:
        # OTLP via gRPC; configuration taken from environment variables
        # e.g., OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317, OTEL_EXPORTER_OTLP_PROTOCOL=grpc
        try:
            exporter = OTLPSpanExporterGRPC()
        except Exception:
            exporter = None

    if exporter is None:
        exporter = ConsoleSpanExporter()

    span_processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(span_processor)
    trace.set_tracer_provider(provider)

    # Instrument libraries
    RequestsInstrumentor().instrument()
    RedisInstrumentor().instrument()
    if flask_app is not None:
        FlaskInstrumentor().instrument_app(flask_app)

    return trace.get_tracer(service_name)

