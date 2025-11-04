import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import random
import time
from flask import Flask, jsonify

from config import Config
from logging_config import setup_logging
from sentry_integration import init_sentry, bind_request_context_to_sentry
from middleware import register_middleware
from error_handlers import register_error_handlers
from utils.errors import AppError, ValidationError
from utils.recovery import retry, CircuitBreaker


def create_app(config: Config | None = None) -> Flask:
    config = config or Config()

    app = Flask(config.APP_NAME)
    app.config.from_mapping(
        ENV=config.ENV,
        DEBUG=config.DEBUG,
        TESTING=config.TESTING,
        JSONIFY_PRETTYPRINT_REGULAR=False,
    )

    setup_logging(config)
    init_sentry(app, config)
    register_middleware(app, config)
    register_error_handlers(app, config)

    # Example in-memory circuit breaker for a flaky upstream/resource
    upstream_breaker = CircuitBreaker(
        name="upstream_service",
        failure_threshold=config.CB_FAILURE_THRESHOLD,
        recovery_timeout=config.CB_RECOVERY_TIMEOUT,
        expected_exceptions=(ConnectionError, TimeoutError),
    )

    @app.route("/healthz")
    def healthz():
        # Lightweight probe. Avoid heavy dependencies and external calls here.
        return jsonify({"status": "ok"}), 200

    def unstable_operation(may_fail_ratio: float = 0.5) -> str:
        # Simulates a flaky call. Replace with actual I/O calls.
        if random.random() < may_fail_ratio:
            # Simulate a transient upstream failure
            raise ConnectionError("upstream connection failed")
        # Simulate some processing latency
        time.sleep(0.05)
        return "success"

    @app.route("/unstable")
    @bind_request_context_to_sentry
    @retry(
        retries=3,
        backoff_factor=0.2,
        jitter=0.1,
        retry_on=(ConnectionError, TimeoutError),
        logger_name="app.recovery",
    )
    @upstream_breaker
    def unstable_endpoint():
        result = unstable_operation()
        return jsonify({"result": result}), 200

    @app.route("/validate")
    @bind_request_context_to_sentry
    def validate():
        # Example of raising a structured application error
        raise ValidationError(message="Invalid query parameter", details={"param": "foo"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(Config().PORT), debug=Config().DEBUG)

