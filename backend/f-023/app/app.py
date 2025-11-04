import os
import random
import time
from flask import Flask, jsonify, request
import requests

from .observability.config import AppConfig
from .observability.logging import init_logging, logger
from .observability.metrics import init_metrics
from .observability.tracing import init_tracing
from .observability.health import health_blueprint


def create_app() -> Flask:
    cfg = AppConfig.from_env()

    init_logging(cfg.LOG_LEVEL)

    app = Flask(__name__)
    app.config["APP_CONFIG"] = cfg

    # Health endpoints
    app.register_blueprint(health_blueprint)

    # Metrics
    init_metrics(app)

    # Tracing (must come after app creation)
    init_tracing(app, cfg)

    @app.route("/")
    def index():
        logger.info("handling_root")
        return jsonify({"status": "ok", "service": cfg.SERVICE_NAME, "environment": cfg.ENVIRONMENT})

    @app.route("/work")
    def work():
        # Simulate unit of work with outbound HTTP to demonstrate tracing
        delay_ms = int(request.args.get("delay_ms", 100))
        delay_ms = max(0, min(delay_ms, 2000))
        logger.info("simulate_work", extra={"delay_ms": delay_ms})
        time.sleep(delay_ms / 1000.0)

        # Outbound call to example endpoint to create a child span (traced via RequestsInstrumentor)
        try:
            _ = requests.get("https://httpbin.org/status/200", timeout=2)
        except Exception as e:
            logger.warning("outbound_http_failed", extra={"error": str(e)})

        payload = {
            "message": "work_done",
            "delay_ms": delay_ms,
            "random_value": random.randint(1, 100),
        }
        logger.info("work_completed", extra=payload)
        return jsonify(payload)

    @app.route("/error")
    def error():
        logger.info("trigger_error")
        try:
            1 / 0
        except Exception as e:
            logger.exception("simulated_error", extra={"error": str(e)})
            return jsonify({"error": "simulated"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)

