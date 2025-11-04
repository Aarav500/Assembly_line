import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import os
import signal
import threading
import time
from typing import Any, Dict, Tuple

from flask import Flask, Response, jsonify, request

import health


# Configure logging
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("healthapp")


def create_app() -> Flask:
    app = Flask(__name__)

    # Initialize health subsystem and dependency checks from env
    health.init_from_env()

    # Register signal handlers for graceful shutdown
    health.register_signal_handlers()

    # Track in-flight requests for graceful shutdown
    @app.before_request
    def _before_request() -> None:
        health.request_started()

    @app.after_request
    def _after_request(response: Response) -> Response:
        health.request_finished()
        return response

    # Health endpoints
    @app.route("/health/live", methods=["GET"])  # Kubernetes livenessProbe
    @app.route("/health/liveness", methods=["GET"])  # alias
    def liveness() -> Tuple[Response, int]:
        ok, info = health.check_liveness()
        status_code = 200 if ok else 500
        return jsonify(info), status_code

    @app.route("/health/ready", methods=["GET"])  # Kubernetes readinessProbe
    @app.route("/health/readiness", methods=["GET"])  # alias
    def readiness() -> Tuple[Response, int]:
        ok, info = health.check_readiness()
        status_code = 200 if ok else 503
        return jsonify(info), status_code

    @app.route("/health/startup", methods=["GET"])  # Kubernetes startupProbe
    def startup() -> Tuple[Response, int]:
        ok, info = health.check_startup()
        status_code = 200 if ok else 503
        return jsonify(info), status_code

    # Optional root route
    @app.route("/", methods=["GET"])  # helpful default
    def root() -> Tuple[Response, int]:
        return jsonify({
            "service": os.environ.get("SERVICE_NAME", "health-check-service"),
            "version": os.environ.get("SERVICE_VERSION", "0.0.1"),
            "endpoints": [
                "/health/live",
                "/health/ready",
                "/health/startup",
            ],
        }), 200

    return app


app = create_app()


if __name__ == "__main__":
    # Development server only. In production use gunicorn with the provided config.
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)  # debug can be enabled with FLASK_ENV=development

