import os
import time
from typing import Optional

from flask import Blueprint, current_app, g, request
from prometheus_client import Counter, Histogram, REGISTRY, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import multiprocess

_METRICS_REGISTERED_APPS = set()

# Define metrics lazily to ensure MultiProcess mode is respected
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path", "status"],
    buckets=(
        0.001, 0.005, 0.01, 0.025, 0.05,
        0.1, 0.25, 0.5, 1.0, 2.5,
        5.0, 10.0
    ),
)


def _normalize_path():
    rule = getattr(request, "url_rule", None)
    if rule and getattr(rule, "rule", None):
        return rule.rule
    # Fallback to raw path but reduce cardinality by stripping IDs (very naive)
    p = request.path
    parts = []
    for part in p.split('/'):
        if part.isdigit() or len(part) >= 16:
            parts.append(":id")
        else:
            parts.append(part)
    return "/".join([x for x in parts if x != ""]) or "/"


def _before_request():
    g._metrics_start_time = time.perf_counter()


def _after_request(response):
    try:
        method = request.method
        path = _normalize_path()
        status = str(response.status_code)
        duration = None
        start = getattr(g, "_metrics_start_time", None)
        if start is not None:
            duration = max(0.0, time.perf_counter() - start)
        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        if duration is not None:
            REQUEST_LATENCY.labels(method=method, path=path, status=status).observe(duration)
    except Exception:
        # Never break the response due to metrics errors
        pass
    return response


def _create_metrics_blueprint(path: str) -> Blueprint:
    bp = Blueprint("__metrics__", __name__)

    @bp.route(path, methods=["GET"])  # type: ignore[misc]
    def metrics_endpoint():
        # Setup multiprocess collector if configured
        if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
            # Ensure the registry aggregates child process metrics
            multiprocess.MultiProcessCollector(REGISTRY)
        data = generate_latest(REGISTRY)
        return current_app.response_class(data, mimetype=CONTENT_TYPE_LATEST)

    return bp


def register_metrics(app, *, path: Optional[str] = None):
    global _METRICS_REGISTERED_APPS
    if id(app) in _METRICS_REGISTERED_APPS:
        return

    metrics_path = path or os.environ.get("METRICS_PATH", "/metrics")

    # Register request hooks
    app.before_request(_before_request)
    app.after_request(_after_request)

    # Register metrics endpoint
    bp = _create_metrics_blueprint(metrics_path)
    app.register_blueprint(bp)

    _METRICS_REGISTERED_APPS.add(id(app))

