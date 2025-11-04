import os
import time
import json
import socket
import logging
from datetime import datetime
from typing import Dict

import requests
from flask import Flask, request, Response, jsonify
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, multiprocess

# Optional OpenTelemetry (enabled when OTEL_EXPORTER_OTLP_ENDPOINT is set)
OTEL_ENABLED = bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))
if OTEL_ENABLED:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        service_name = os.environ.get("SERVICE_NAME", "mesh-demo")
        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        span_exporter = OTLPSpanExporter()
        span_processor = BatchSpanProcessor(span_exporter)
        provider.add_span_processor(span_processor)
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)
    except Exception as e:
        OTEL_ENABLED = False
        print(f"OpenTelemetry init failed: {e}")

app = Flask(__name__)

# Logging setup (JSON to stdout)
class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "level": record.levelname,
            "time": datetime.utcnow().isoformat() + "Z",
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "extra_fields"):
            data.update(record.extra_fields)
        return json.dumps(data)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
app.logger.setLevel(logging.INFO)
app.logger.handlers = [handler]

# Prometheus metrics
registry = CollectorRegistry()
if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
    multiprocess.MultiProcessCollector(registry)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "http_status"],
    registry=registry,
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    registry=registry,
)
INFLIGHT = Gauge(
    "http_inflight_requests",
    "In-flight HTTP requests",
    ["endpoint"],
    registry=registry,
)
OUTBOUND_LATENCY = Histogram(
    "outbound_request_duration_seconds",
    "Outbound request latency",
    ["target"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    registry=registry,
)
OUTBOUND_ERRORS = Counter(
    "outbound_request_errors_total",
    "Outbound request errors",
    ["target", "reason"],
    registry=registry,
)

# Config
APP_NAME = os.environ.get("SERVICE_NAME", "mesh-demo")
APP_VERSION = os.environ.get("APP_VERSION", "v1")
DOWNSTREAM_URL = os.environ.get("DOWNSTREAM_URL", "")
REQUEST_TIMEOUT_MS = int(os.environ.get("REQUEST_TIMEOUT_MS", "1000"))
PORT = int(os.environ.get("PORT", "8080"))

HOSTNAME = socket.gethostname()

TRACE_HEADERS = [
    # W3C TraceContext
    "traceparent",
    "tracestate",
    # B3
    "x-b3-traceid",
    "x-b3-spanid",
    "x-b3-parentspanid",
    "x-b3-sampled",
    "x-b3-flags",
    # Envoy/others
    "x-request-id",
    "x-ot-span-context",
]

if OTEL_ENABLED:
    try:
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
    except Exception as e:
        app.logger.warning("OTel instrumentation failed", extra={"extra_fields": {"error": str(e)}})


def extract_trace_context(headers: Dict[str, str]) -> Dict[str, str]:
    return {h: headers.get(h, "") for h in TRACE_HEADERS if h in headers}


def with_trace_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for h in TRACE_HEADERS:
        if h in headers:
            out[h] = headers[h]
    return out


@app.before_request
def before_request():
    request._start_time = time.time()
    INFLIGHT.labels(endpoint=request.path).inc()


@app.after_request
def after_request(response: Response):
    try:
        latency = time.time() - getattr(request, "_start_time", time.time())
        REQUEST_LATENCY.labels(method=request.method, endpoint=request.path).observe(latency)
        REQUEST_COUNT.labels(method=request.method, endpoint=request.path, http_status=response.status_code).inc()
    finally:
        INFLIGHT.labels(endpoint=request.path).dec()
    return response


@app.route("/healthz")
def healthz():
    return Response("ok", status=200)


@app.route("/readyz")
def readyz():
    # Simple readiness; extend with dependency checks as needed
    return Response("ready", status=200)


@app.route("/metrics")
def metrics():
    return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)


@app.route("/headers")
def headers():
    return jsonify({k.lower(): v for k, v in request.headers.items()})


@app.route("/")
def root():
    payload = {
        "service": APP_NAME,
        "version": APP_VERSION,
        "hostname": HOSTNAME,
        "time": datetime.utcnow().isoformat() + "Z",
        "downstream_configured": bool(DOWNSTREAM_URL),
        "trace": extract_trace_context({k.lower(): v for k, v in request.headers.items()}),
    }
    return jsonify(payload)


@app.route("/echo")
def echo():
    msg = request.args.get("msg", "hello")
    return jsonify({
        "echo": msg,
        "service": APP_NAME,
        "version": APP_VERSION,
    })


@app.route("/sleep")
def sleep():
    ms = int(request.args.get("ms", "100"))
    ms = max(0, min(ms, 60000))
    time.sleep(ms / 1000.0)
    return jsonify({"slept_ms": ms})


@app.route("/outgoing")
def outgoing():
    if not DOWNSTREAM_URL:
        return jsonify({"error": "DOWNSTREAM_URL not set"}), 400

    path = request.args.get("path", "/")
    # Sanitize path
    if not path.startswith("/"):
        path = "/" + path

    url = DOWNSTREAM_URL.rstrip("/") + path
    timeout = REQUEST_TIMEOUT_MS / 1000.0

    headers = with_trace_headers({k.lower(): v for k, v in request.headers.items()})
    start = time.time()
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        duration = time.time() - start
        OUTBOUND_LATENCY.labels(target=DOWNSTREAM_URL).observe(duration)
        r.raise_for_status()
        body = None
        try:
            body = r.json()
        except Exception:
            body = r.text
        return jsonify({
            "service": APP_NAME,
            "version": APP_VERSION,
            "downstream_url": url,
            "downstream_status": r.status_code,
            "downstream_body": body,
            "duration_ms": int(duration * 1000),
        })
    except requests.exceptions.Timeout as e:
        OUTBOUND_ERRORS.labels(target=DOWNSTREAM_URL, reason="timeout").inc()
        app.logger.warning("downstream timeout", extra={"extra_fields": {"url": url, "timeout_ms": REQUEST_TIMEOUT_MS}})
        return jsonify({"error": "downstream timeout", "url": url}), 504
    except requests.exceptions.RequestException as e:
        OUTBOUND_ERRORS.labels(target=DOWNSTREAM_URL, reason="error").inc()
        app.logger.error("downstream error", extra={"extra_fields": {"url": url, "error": str(e)}})
        status = 502
        if hasattr(e, "response") and e.response is not None:
            status = e.response.status_code
        return jsonify({"error": "downstream error", "url": url, "detail": str(e)}), status


def create_app():
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

