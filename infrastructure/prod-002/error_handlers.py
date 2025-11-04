import logging
from datetime import datetime, timezone
from flask import jsonify
from werkzeug.exceptions import HTTPException

from config import Config
from context import get_request_id, get_correlation_id
from utils.errors import AppError
from utils.sanitization import sanitize_exception_text

logger = logging.getLogger("app.errors")


def _error_payload(status: int, code: str, message: str, details=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "request_id": get_request_id(),
        "correlation_id": get_correlation_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
    }


def register_error_handlers(app, config: Config):
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        logger.warning(
            f"application error: {err.code}",
            extra={"extra": {"code": err.code, "details": err.details, "http_status": err.http_status}},
        )
        payload = _error_payload(err.http_status, err.code, err.message, err.details)
        return jsonify(payload), err.http_status

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        code = getattr(err, "code", 500) or 500
        description = getattr(err, "description", "HTTP error")
        payload = _error_payload(code, f"HTTP_{code}", str(description))
        # 4xx typical; avoid noisy stack traces
        if 500 <= code < 600:
            logger.error("http exception", extra={"extra": {"code": code, "description": description}}, exc_info=err)
        else:
            logger.info("client error", extra={"extra": {"code": code, "description": description}})
        return jsonify(payload), code

    @app.errorhandler(Exception)
    def handle_unhandled_exception(err: Exception):
        logger.exception("unhandled exception", extra={"extra": {"exc": sanitize_exception_text(err)}})
        payload = _error_payload(500, "INTERNAL_SERVER_ERROR", "An unexpected error occurred")
        return jsonify(payload), 500

