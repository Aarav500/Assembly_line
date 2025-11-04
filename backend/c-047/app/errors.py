"""
Centralized error handling utilities.

Developer explanation:
- Flask lets you register handlers for specific exceptions or HTTP codes.
- Centralizing them ensures consistent JSON error shapes across the API.
- Keep error responses concise in production; optionally include debug context in development.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from flask import Flask, jsonify, request


def register_error_handlers(app: Flask) -> None:
    """Register common error handlers on the provided app instance."""

    @app.errorhandler(400)
    def handle_400(error) -> Tuple[Any, int]:  # type: ignore[override]
        return _json_error("bad_request", str(getattr(error, "description", "Bad Request")), app, 400)

    @app.errorhandler(404)
    def handle_404(error) -> Tuple[Any, int]:  # type: ignore[override]
        return _json_error("not_found", "The requested resource was not found.", app, 404)

    @app.errorhandler(405)
    def handle_405(error) -> Tuple[Any, int]:  # type: ignore[override]
        return _json_error("method_not_allowed", "HTTP method not allowed on this route.", app, 405)

    @app.errorhandler(500)
    def handle_500(error) -> Tuple[Any, int]:  # type: ignore[override]
        return _json_error("internal_server_error", "An unexpected error occurred.", app, 500)

    # Example: transform generic exceptions to JSON in production while letting them surface in debug.
    @app.errorhandler(Exception)
    def handle_exception(error) -> Tuple[Any, int]:  # type: ignore[override]
        if app.config.get("DEBUG"):
            # In debug mode, let Flask's debugger show rich information.
            raise error
        return _json_error("unhandled_exception", "An unexpected error occurred.", app, 500)


def _json_error(code: str, message: str, app: Flask, status: int) -> Tuple[Any, int]:
    """
    Helper to build a consistent JSON error response.

    Developer explanation:
    - The shape {"error": {"code", "message", "meta"?}} is simple and extensible.
    - Avoid leaking sensitive details; only include debug metadata when explicitly enabled.
    """
    payload: Dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }

    # Optionally include request context and environment details; never enable in production.
    if app.config.get("INCLUDE_DEBUG_META"):
        payload["error"]["meta"] = {
            "path": request.path,
            "method": request.method,
            "environment": app.config.get("ENV"),
        }

    return jsonify(payload), status

