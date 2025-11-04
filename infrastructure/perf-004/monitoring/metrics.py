import time
from typing import Optional

from flask import current_app, g, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

# HTTP server metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Database pool metrics
db_connections_created_total = Counter(
    "db_connections_created_total", "Total DB connections created by pool"
)
db_checkouts_total = Counter(
    "db_checkouts_total", "Total DB connection checkouts from pool"
)
db_checkout_errors_total = Counter(
    "db_checkout_errors_total", "Total DB checkout errors"
)
db_pool_size_gauge = Gauge(
    "db_pool_size", "Configured DB pool size (base size, without overflow)"
)
db_pool_overflow_gauge = Gauge(
    "db_pool_overflow", "Current DB pool overflow (connections above pool size)"
)
db_pool_checked_out_gauge = Gauge(
    "db_pool_checked_out", "Current number of DB connections checked out"
)

# Redis pool metrics
redis_pool_in_use_gauge = Gauge(
    "redis_pool_in_use", "Current number of Redis connections in use"
)
redis_pool_max_connections_gauge = Gauge(
    "redis_pool_max_connections", "Configured Redis max connections"
)

# External HTTP client metrics
http_client_in_flight_gauge = Gauge(
    "http_client_in_flight", "Number of in-flight outbound HTTP requests"
)
http_client_requests_total = Counter(
    "http_client_requests_total", "Total outbound HTTP requests", ["method", "host", "status"]
)
http_client_errors_total = Counter(
    "http_client_errors_total", "Total errors for outbound HTTP requests", ["method", "host", "error"]
)
http_client_request_duration_seconds = Histogram(
    "http_client_request_duration_seconds",
    "Outbound HTTP request latency in seconds",
    ["method", "host", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)


def _get_endpoint_name() -> str:
    try:
        return (getattr(g, "_endpoint_name", None) or
                (current_app.request_class.endpoint if hasattr(current_app, "request_class") else None) or
                (getattr(g, "request", None) and getattr(g.request, "endpoint", "unknown")) or
                (getattr(g, "endpoint", None)) or "unknown")
    except Exception:
        return "unknown"


def init_metrics(app):
    if not app.config.get("METRICS_ENABLED", True):
        return

    @app.before_request
    def _start_timer():
        g._metrics_start_time = time.perf_counter()

    @app.after_request
    def _after(response):
        try:
            start = getattr(g, "_metrics_start_time", None)
            if start is not None:
                dur = time.perf_counter() - start
                method = getattr(getattr(g, "request", None), "method", None) or getattr(getattr(app, "request_class", None), "method", "").upper() or "UNKNOWN"
                endpoint = (getattr(getattr(g, "request", None), "endpoint", None) or getattr(getattr(app, "request_class", None), "endpoint", None) or getattr(getattr(app, "request_context", None), "endpoint", None) or request_path_safe())
                status = str(response.status_code)
                http_request_duration_seconds.labels(method=method, endpoint=endpoint, status=status).observe(dur)
                http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        except Exception:
            # Never fail the request due to metrics
            pass
        return response

    def request_path_safe() -> str:
        try:
            from flask import request
            return request.endpoint or (request.path or "unknown")
        except Exception:
            return "unknown"

    @app.route(app.config.get("METRICS_ROUTE", "/metrics"))
    def metrics() -> Response:
        try:
            update_runtime_gauges(app)
            output = generate_latest()
            return Response(output, mimetype=CONTENT_TYPE_LATEST)
        except Exception as exc:
            return Response(f"metrics collection error: {exc}", status=500)


def update_runtime_gauges(app: Optional[object] = None):
    """Update gauges from live pool state. Called at scrape time."""
    try:
        from flask import current_app as cap
        app = app or cap
    except Exception:
        pass
    if app is None:
        return

    # DB gauges
    try:
        engine = app.extensions.get("db_engine")
        if engine is not None and hasattr(engine, "pool"):
            pool = engine.pool
            # Set static configured size once if available
            try:
                size = getattr(pool, "size", lambda: None)()
                if size is not None:
                    db_pool_size_gauge.set(size)
            except Exception:
                pass
            try:
                checked_out = getattr(pool, "checkedout", lambda: None)()
                if checked_out is not None:
                    db_pool_checked_out_gauge.set(checked_out)
            except Exception:
                pass
            try:
                overflow = getattr(pool, "overflow", lambda: None)()
                if overflow is not None:
                    db_pool_overflow_gauge.set(overflow)
            except Exception:
                pass
    except Exception:
        pass

    # Redis gauges
    try:
        rpool = app.extensions.get("redis_pool")
        if rpool is not None:
            try:
                max_conns = getattr(rpool, "max_connections", None)
                if max_conns is not None:
                    redis_pool_max_connections_gauge.set(max_conns)
            except Exception:
                pass
            try:
                in_use = 0
                if hasattr(rpool, "_in_use_connections"):
                    in_use = len(getattr(rpool, "_in_use_connections", []))
                elif hasattr(rpool, "_created_connections") and hasattr(rpool, "max_connections"):
                    # Fallback approximate measure
                    created = getattr(rpool, "_created_connections")
                    available = len(getattr(rpool, "_available_connections", []))
                    in_use = max(0, created - available)
                redis_pool_in_use_gauge.set(in_use)
            except Exception:
                pass
    except Exception:
        pass

    # HTTP client gauges are updated during operations; no periodic updates here.

