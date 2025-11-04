import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import logging
from random import random

import requests
from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, Histogram
from opentelemetry import trace

from telemetry import init_telemetry


SERVICE_NAME = os.getenv("SERVICE_NAME", "flask-telemetry-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")


# Custom application metrics
WORK_DURATION = Histogram(
    "app_work_duration_seconds",
    "Duration of work() endpoint processing in seconds",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
WORK_ITEMS = Counter(
    "app_work_items_total", "Total work items processed", ["result"]
)
BUSINESS_EVENTS = Counter(
    "app_business_events_total", "Count of business events", ["event", "status"]
)


def create_app() -> Flask:
    app = Flask(__name__)

    # Initialize telemetry: tracing + logs
    init_telemetry(app)

    # Prometheus metrics exporter (exposes /metrics)
    metrics = PrometheusMetrics(app, group_by="endpoint")
    metrics.info(
        "app_info",
        "Application info",
        version=SERVICE_VERSION,
        service=SERVICE_NAME,
        environment=ENVIRONMENT,
    )

    tracer = trace.get_tracer(SERVICE_NAME)
    logger = logging.getLogger(SERVICE_NAME)

    @app.route("/healthz")
    def healthz():
        return jsonify(status="ok", service=SERVICE_NAME, version=SERVICE_VERSION)

    @app.route("/")
    def index():
        logger.info("Index requested")
        BUSINESS_EVENTS.labels(event="index", status="hit").inc()
        return jsonify(
            message="Hello, telemetry!",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            environment=ENVIRONMENT,
        )

    @app.route("/work")
    def work():
        # Optional complexity parameter
        n = int(request.args.get("n", "5"))
        simulate_http = request.args.get("http", "1") == "1"

        with tracer.start_as_current_span("work_handler") as span:
            span.set_attribute("work.n", n)
            start = time.perf_counter()
            total = 0

            try:
                # Simulate compute-bound work
                for i in range(n):
                    # Busy-ish loop work simulation
                    time.sleep(0.02 + random() * 0.02)
                    total += i * i

                # Simulate an outbound HTTP dependency to demonstrate tracing/metrics
                if simulate_http:
                    try:
                        r = requests.get("https://httpbin.org/delay/0.1", timeout=2)
                        span.set_attribute("httpbin.status_code", r.status_code)
                    except Exception as dep_err:
                        logger.warning("HTTP dependency failed", exc_info=dep_err)
                        span.set_attribute("httpbin.error", True)

                duration = time.perf_counter() - start
                WORK_DURATION.observe(duration)
                WORK_ITEMS.labels(result="success").inc()

                logger.info(
                    "Work completed",
                    extra={
                        "work_n": n,
                        "duration_sec": round(duration, 4),
                        "total": total,
                    },
                )

                return jsonify(result=total, duration_sec=duration, n=n)

            except Exception as e:
                duration = time.perf_counter() - start
                WORK_DURATION.observe(duration)
                WORK_ITEMS.labels(result="error").inc()
                span.record_exception(e)
                span.set_attribute("work.error", True)
                logger.exception("Work failed")
                return (
                    jsonify(error=str(e), duration_sec=duration),
                    500,
                )

    return app


if __name__ == "__main__":
    app = create_app()
    host = os.getenv("BIND_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    app.run(host=host, port=port)



@app.route('/users/42', methods=['GET'])
def _auto_stub_users_42():
    return 'Auto-generated stub for /users/42', 200
