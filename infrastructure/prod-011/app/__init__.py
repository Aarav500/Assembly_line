import logging
import os
import threading
import time
from typing import Tuple

from flask import Flask, jsonify, request, g


# Configure basic logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(threadName)s %(name)s - %(message)s",
)
logger = logging.getLogger("graceful-app")


class GracefulState:
    def __init__(self):
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._active_requests = 0
        self._draining = threading.Event()

    def is_draining(self) -> bool:
        return self._draining.is_set()

    def start_draining(self) -> None:
        if not self._draining.is_set():
            logger.info("Starting draining: marking app as shutting down (unhealthy)")
            self._draining.set()

    def increment_active(self) -> None:
        with self._lock:
            self._active_requests += 1
            logger.debug("Active requests incremented to %d", self._active_requests)

    def decrement_active(self) -> None:
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            logger.debug("Active requests decremented to %d", self._active_requests)
            if self._active_requests == 0:
                self._cond.notify_all()

    def wait_for_zero(self, timeout: float) -> Tuple[bool, int]:
        deadline = time.time() + timeout
        with self._lock:
            while self._active_requests > 0:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False, self._active_requests
                self._cond.wait(timeout=remaining)
            return True, 0

    def get_active(self) -> int:
        with self._lock:
            return self._active_requests


state = GracefulState()


def create_app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def before_request():
        # Don't count health checks as active requests to avoid blocking drain
        is_health = request.path.startswith("/healthz")

        # If draining, reject new requests (except health which should reflect draining state)
        if not is_health and state.is_draining():
            return (
                jsonify({
                    "status": "shutting_down",
                    "message": "Server is draining connections and not accepting new requests",
                }),
                503,
            )

        # Mark counted so we can reliably decrement in after_request
        if not is_health:
            g._counted_active_request = True
            state.increment_active()
        else:
            g._counted_active_request = False

    @app.after_request
    def after_request(response):
        if getattr(g, "_counted_active_request", False):
            state.decrement_active()
            g._counted_active_request = False
        return response

    @app.errorhandler(Exception)
    def handle_error(err):
        logger.exception("Unhandled exception during request: %s", err)
        # Ensure counter decremented if after_request didn't run
        if getattr(g, "_counted_active_request", False):
            state.decrement_active()
            g._counted_active_request = False
        return jsonify({"error": str(err)}), 500

    @app.get("/healthz")
    def healthz():
        if state.is_draining():
            return jsonify({"status": "draining", "active_requests": state.get_active()}), 503
        return jsonify({"status": "ok", "active_requests": state.get_active()}), 200

    @app.get("/")
    def index():
        return jsonify({"message": "Hello, world!", "draining": state.is_draining()}), 200

    @app.get("/work")
    def work():
        try:
            # Simulate some work to demonstrate graceful draining
            duration = float(request.args.get("duration", "2"))
            # Cap duration to avoid tests hanging
            duration = max(0.0, min(duration, 60.0))
        except ValueError:
            return jsonify({"error": "invalid duration"}), 400

        logger.info("Starting work for %.2f seconds", duration)
        time.sleep(duration)
        logger.info("Finished work for %.2f seconds", duration)
        return jsonify({"status": "done", "slept": duration}), 200

    # Attach helpers for server control
    app.graceful_state = state
    app.start_draining = state.start_draining
    app.wait_for_zero = state.wait_for_zero
    app.get_active = state.get_active

    return app


# Create a default app instance for convenience
app = create_app()

