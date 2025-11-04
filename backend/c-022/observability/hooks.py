import logging
import os
import re
import time
import uuid
from contextlib import suppress

from flask import g, request, Response

# Metrics (Prometheus)
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import CollectorRegistry
from prometheus_client import multiprocess

# OpenTelemetry tracing
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# JSON logging
from pythonjsonlogger import jsonlogger


def _bool_env(name: str, default: bool = True) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _float_env(name: str, default: float) -> float:
    with suppress(Exception):
        return float(os.getenv(name, str(default)))
    return default


class _TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Attach OpenTelemetry trace/span IDs if present
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            record.trace_id = f"{ctx.trace_id:032x}"
            record.span_id = f"{ctx.span_id:016x}"
            record.trace_flags = int(ctx.trace_flags)
        else:
            record.trace_id = ""
            record.span_id = ""
            record.trace_flags = 0
        # Add request ID if available
        try:
            record.request_id = getattr(g, "request_id", "")
            record.http_method = getattr(request, "method", "")
            record.http_path = getattr(request, "path", "")
            record.remote_addr = request.headers.get("X-Forwarded-For", request.remote_addr) if request else ""
        except Exception:
            record.request_id = ""
            record.http_method = ""
            record.http_path = ""
            record.remote_addr = ""
        return True


def _init_logging(service_name: str) -> None:
    level_name = os.getenv("LOG_LEVEL", os.getenv("OBS_LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(level)
    # Clear existing handlers to avoid duplicate logs in reload scenarios
    logger.handlers.clear()

    handler = logging.StreamHandler()

    # JSON formatter with sane defaults
    fmt_keys = [
        "levelname",
        "name",
        "message",
        "asctime",
        "trace_id",
        "span_id",
        "request_id",
        "http_method",
        "http_path",
        "remote_addr",
        "trace_flags",
        "pathname",
        "lineno",
        "funcName",
        "processName",
        "threadName",
    ]
    fmt = jsonlogger.JsonFormatter(" ".join([f"%({k})s" for k in fmt_keys]))
    handler.setFormatter(fmt)

    handler.addFilter(_TraceContextFilter())
    logger.addHandler(handler)

    # Reduce noisy loggers if desired
    for noisy in [
        "werkzeug",
        "urllib3",
        "opentelemetry",
    ]:
        logging.getLogger(noisy).setLevel(getattr(logging, os.getenv("NOISY_LOG_LEVEL", "WARNING")))

    logging.getLogger(__name__).info("logging initialized", extra={"service_name": service_name})


def _canonical_endpoint() -> str:
    try:
        # Prefer Flask's matched endpoint "blueprint.view_func". If unavailable, fallback to path template-ish.
        ep = request.endpoint or "unknown"
        if not ep:
            return "unknown"
        return ep
    except Exception:
        return "unknown"


# Prometheus metrics definitions (created on first init)
_HTTP_REQUESTS = None
_HTTP_LATENCY = None
_HTTP_INPROGRESS = None
_APP_INFO = None


def _init_metrics():
    global _HTTP_REQUESTS, _HTTP_LATENCY, _HTTP_INPROGRESS, _APP_INFO
    if _HTTP_REQUESTS is not None:
        return

    _HTTP_REQUESTS = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )

    _HTTP_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint", "status"],
        buckets=[
            0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1,
            0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0
        ],
    )

    _HTTP_INPROGRESS = Gauge(
        "http_inprogress_requests",
        "In-progress HTTP requests",
        ["endpoint"],
    )

    _APP_INFO = Gauge(
        "app_info",
        "Static information about the running application",
        ["service_name"],
    )


def _metrics_endpoint():
    # If multiprocess mode is enabled, use a dedicated registry
    mp_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if mp_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        data = generate_latest(registry)
    else:
        data = generate_latest()
    return Response(data, mimetype=CONTENT_TYPE_LATEST)


def _normalize_status(status_code) -> str:
    try:
        return str(int(status_code))
    except Exception:
        return str(status_code)


def _maybe_set_request_id(resp):
    try:
        rid_header = os.getenv("REQUEST_ID_HEADER", "X-Request-ID")
        if getattr(g, "request_id", None):
            resp.headers[rid_header] = g.request_id
    except Exception:
        pass
    return resp


def _init_tracing(service_name: str):
    # Respect env toggles and standard OTEL variables
    sampling_prob = _float_env("OTEL_TRACES_SAMPLER_ARG", _float_env("OBS_SAMPLING_PROB", 1.0))
    sampler = ParentBased(TraceIdRatioBased(sampling_prob))

    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("SERVICE_VERSION", "0.0.1"),
        "service.instance.id": os.getenv("HOSTNAME", str(uuid.uuid4())),
        "deployment.environment": os.getenv("ENV", os.getenv("ENVIRONMENT", "dev")),
    })

    provider = TracerProvider(resource=resource, sampler=sampler)

    # Prefer OTEL_EXPORTER_OTLP_ENDPOINT, fallback to OBS_OTLP_ENDPOINT
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv("OBS_OTLP_ENDPOINT")

    exporter = None
    if endpoint:
        # If endpoint lacks scheme, assume http
        if not re.match(r"^[a-zA-Z]+://", endpoint):
            endpoint = f"http://{endpoint}"
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        exporter = ConsoleSpanExporter()

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Auto-instrument popular libs
    RequestsInstrumentor().instrument()


class _Observability:
    def __init__(self, app):
        self.app = app
        self.service_name = (
            os.getenv("OTEL_SERVICE_NAME")
            or os.getenv("OBS_SERVICE_NAME")
            or app.import_name
        )

        if _bool_env("OBS_ENABLE_LOGGING", True):
            _init_logging(self.service_name)

        if _bool_env("OBS_ENABLE_TRACING", True):
            _init_tracing(self.service_name)
            # Instrument Flask after provider is set
            FlaskInstrumentor().instrument_app(app)

        if _bool_env("OBS_ENABLE_METRICS", True):
            _init_metrics()
            self._install_metrics_hooks()
            self._register_metrics_route()
            # Mark app info gauge once
            try:
                _APP_INFO.labels(service_name=self.service_name).set(1)
            except Exception:
                pass

        # Always add request/response logging hooks
        self._install_logging_hooks()

    def _register_metrics_route(self):
        endpoint = os.getenv("METRICS_ENDPOINT", "/metrics")

        # Avoid duplicate registration when using auto-reload
        if endpoint in {rule.rule for rule in self.app.url_map.iter_rules()}:
            return

        @self.app.route(endpoint)
        def metrics():
            return _metrics_endpoint()

    def _install_metrics_hooks(self):
        @self.app.before_request
        def _before_request():
            g._obs_start_time = time.perf_counter()
            # request id
            rid_header = os.getenv("REQUEST_ID_HEADER", "X-Request-ID")
            g.request_id = request.headers.get(rid_header) or str(uuid.uuid4())
            # in-progress
            try:
                _HTTP_INPROGRESS.labels(endpoint=_canonical_endpoint()).inc()
            except Exception:
                pass

        @self.app.after_request
        def _after_request(response):
            try:
                duration = max(time.perf_counter() - getattr(g, "_obs_start_time", time.perf_counter()), 0.0)
                method = request.method
                endpoint = _canonical_endpoint()
                status = _normalize_status(response.status_code)

                _HTTP_REQUESTS.labels(method=method, endpoint=endpoint, status=status).inc()
                _HTTP_LATENCY.labels(method=method, endpoint=endpoint, status=status).observe(duration)
            except Exception:
                pass
            finally:
                with suppress(Exception):
                    _HTTP_INPROGRESS.labels(endpoint=_canonical_endpoint()).dec()

            return _maybe_set_request_id(response)

        @self.app.teardown_request
        def _teardown_request(exc):
            # Ensure gauge is decremented on teardown in case of exceptions before after_request
            with suppress(Exception):
                _HTTP_INPROGRESS.labels(endpoint=_canonical_endpoint()).dec()

    def _install_logging_hooks(self):
        @self.app.before_request
        def _log_request():
            logging.getLogger(__name__).info(
                "request.received",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "query": request.query_string.decode("utf-8", errors="ignore"),
                    "user_agent": request.headers.get("User-Agent", ""),
                },
            )

        @self.app.after_request
        def _log_response(response):
            try:
                duration = max(time.perf_counter() - getattr(g, "_obs_start_time", time.perf_counter()), 0.0)
            except Exception:
                duration = 0.0
            logging.getLogger(__name__).info(
                "request.completed",
                extra={
                    "status_code": getattr(response, "status_code", 0),
                    "duration_ms": round(duration * 1000.0, 3),
                    "content_length": response.calculate_content_length() if hasattr(response, "calculate_content_length") else None,
                },
            )
            return response

        @self.app.errorhandler(Exception)
        def _log_exception(err):
            logging.getLogger(__name__).exception("request.error", exc_info=err)
            # Let Flask default handler build the response
            return err


def init_observability(app) -> None:
    """
    Initialize observability for a Flask app.

    Features:
    - JSON logging with trace/span and request IDs
    - OpenTelemetry tracing (OTLP exporter or console) with Flask/Requests auto-instrumentation
    - Prometheus metrics with /metrics endpoint and automatic HTTP request metrics

    Environment variables:
    - OBS_ENABLE_LOGGING=true|false
    - OBS_ENABLE_TRACING=true|false
    - OBS_ENABLE_METRICS=true|false
    - OTEL_SERVICE_NAME / OBS_SERVICE_NAME
    - OTEL_EXPORTER_OTLP_ENDPOINT (e.g., http://otel-collector:4318)
    - OTEL_TRACES_SAMPLER_ARG (probability 0.0-1.0)
    - REQUEST_ID_HEADER (default: X-Request-ID)
    - METRICS_ENDPOINT (default: /metrics)
    - LOG_LEVEL (default: INFO)
    - PROMETHEUS_MULTIPROC_DIR (optional for Gunicorn multi-worker)
    """
    _Observability(app)

