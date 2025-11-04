import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

_TRACING_SETUP = False
_FLASK_INSTRUMENTED = False
_REQUESTS_INSTRUMENTED = False


def _get_service_name():
    return (
        os.environ.get("OTEL_SERVICE_NAME")
        or os.environ.get("SERVICE_NAME")
        or "flask-app"
    )


def setup_tracing():
    global _TRACING_SETUP
    if _TRACING_SETUP:
        return

    service_name = _get_service_name()
    service_version = os.environ.get("SERVICE_VERSION")
    deployment_env = os.environ.get("ENVIRONMENT")

    resource = Resource.create(
        {
            "service.name": service_name,
            **({"service.version": service_version} if service_version else {}),
            **(
                {"deployment.environment": deployment_env}
                if deployment_env
                else {}
            ),
        }
    )

    # Sampling ratio (0.0 - 1.0)
    try:
        ratio = float(os.environ.get("TRACE_SAMPLING_RATIO", "1.0"))
    except ValueError:
        ratio = 1.0

    provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(ratio)))

    # Exporter: prefer OTLP/HTTP, fallback to OTLP/gRPC if not available
    exporter = None
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPExporter
        exporter = HTTPExporter()
    except Exception:  # noqa: S110
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCExporter
            exporter = GRPCExporter()
        except Exception:  # noqa: S110
            logging.getLogger(__name__).warning("No OTLP exporter available for tracing; spans will not be exported")

    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    _TRACING_SETUP = True


def instrument_flask(flask_app=None):
    global _FLASK_INSTRUMENTED
    if _FLASK_INSTRUMENTED:
        return

    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
    except Exception:  # noqa: S110
        logging.getLogger(__name__).warning("opentelemetry-instrumentation-flask not installed")
        return

    excluded = os.environ.get("OTEL_PYTHON_FLASK_EXCLUDED_URLS", "/metrics,/healthz,/favicon.ico")

    if flask_app is not None:
        FlaskInstrumentor().instrument_app(flask_app, excluded_urls=excluded)
    else:
        FlaskInstrumentor().instrument(excluded_urls=excluded)

    _FLASK_INSTRUMENTED = True


def instrument_http_clients():
    global _REQUESTS_INSTRUMENTED
    if _REQUESTS_INSTRUMENTED:
        return

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        RequestsInstrumentor().instrument()
        _REQUESTS_INSTRUMENTED = True
    except Exception:  # noqa: S110
        logging.getLogger(__name__).warning("opentelemetry-instrumentation-requests not installed")

