import time
from typing import Optional

from flask import Blueprint, Response, current_app, g, request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Define Prometheus metrics with low-cardinality labels
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route", "http_status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route", "http_status"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)


metrics_blueprint = Blueprint("metrics", __name__)


@metrics_blueprint.route("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


def _get_route() -> str:
    try:
        rule = request.url_rule
        if rule and rule.rule:
            return rule.rule
    except Exception:
        pass
    # Fallback to path, but avoid high cardinality by trimming digits
    return "/unknown"


def before_request():
    g.__request_start_time = time.perf_counter()


def after_request(response):
    try:
        start: Optional[float] = getattr(g, "__request_start_time", None)
        latency = None
        if start is not None:
            latency = max(0.0, time.perf_counter() - start)

        route = _get_route()
        labels = {
            "method": request.method,
            "route": route,
            "http_status": str(response.status_code),
        }
        REQUEST_COUNT.labels(**labels).inc()
        if latency is not None:
            REQUEST_LATENCY.labels(**labels).observe(latency)
    except Exception:
        pass
    return response


def init_metrics(app):
    if not app.config.get("APP_CONFIG") or not app.config["APP_CONFIG"].METRICS_ENABLED:
        return
    # Register blueprint and request hooks
    app.register_blueprint(metrics_blueprint)
    app.before_request(before_request)
    app.after_request(after_request)

