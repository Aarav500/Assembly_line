import logging
import time
import uuid
from flask import g, request
from typing import Callable

from config import Config
from context import set_request_id, set_correlation_id, get_request_id, get_correlation_id


logger = logging.getLogger("app.middleware")


def register_middleware(app, config: Config) -> None:
    @app.before_request
    def _before_request():
        g._start_ts = time.time()

        # Prefer incoming IDs if trusted; otherwise, generate new
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        corr_id = request.headers.get("X-Correlation-ID") or req_id
        set_request_id(req_id)
        set_correlation_id(corr_id)

        # Attach to response later
        g.request_id = req_id
        g.correlation_id = corr_id

    @app.after_request
    def _after_request(response):
        duration_ms = int((time.time() - getattr(g, "_start_ts", time.time())) * 1000)
        # Echo IDs back to clients
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers["X-Correlation-ID"] = getattr(g, "correlation_id", "")

        logger.info(
            "request completed",
            extra={
                "extra": {
                    "event": "request_completed",
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
                }
            },
        )
        return response

    @app.teardown_request
    def _teardown_request(exc):
        # Clear context vars if needed (contextvars typically auto-handle per-request)
        pass

