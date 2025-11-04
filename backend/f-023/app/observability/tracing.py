from typing import Optional

from flask import Flask

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from .config import AppConfig


def init_tracing(app: Flask, cfg: AppConfig):
    if not cfg.TRACING_ENABLED:
        return

    resource = Resource.create(
        {
            "service.name": cfg.SERVICE_NAME,
            "service.version": cfg.SERVICE_VERSION,
            "deployment.environment": cfg.ENVIRONMENT,
            "telemetry.sdk.language": "python",
        }
    )

    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter (gRPC)
    exporter = OTLPSpanExporter(endpoint=cfg.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Instrument Flask and Requests with the configured provider
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()

