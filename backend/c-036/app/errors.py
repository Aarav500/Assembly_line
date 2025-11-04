from __future__ import annotations
from flask import jsonify
from werkzeug.exceptions import HTTPException, NotFound, MethodNotAllowed, BadRequest


class ApiError(HTTPException):
    code = 400
    description = "Bad Request"

    def __init__(self, description: str | None = None, code: int | None = None, extra: dict | None = None):
        super().__init__(description or self.description)
        if code:
            self.code = code
        self.extra = extra or {}


def _problem_json(status: int, title: str, detail: str | None = None, type_url: str | None = None, extra: dict | None = None):
    payload = {
        "type": type_url or "about:blank",
        "title": title,
        "status": status,
    }
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    return jsonify(payload), status, {"Content-Type": "application/problem+json"}


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return _problem_json(err.code or 400, "API Error", str(err.description), extra=err.extra)

    @app.errorhandler(BadRequest)
    def handle_bad_request(err: BadRequest):
        return _problem_json(400, "Bad Request", str(err.description))

    @app.errorhandler(NotFound)
    def handle_not_found(err: NotFound):
        return _problem_json(404, "Not Found", "Resource not found")

    @app.errorhandler(MethodNotAllowed)
    def handle_method_not_allowed(err: MethodNotAllowed):
        return _problem_json(405, "Method Not Allowed", str(err.description))

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("Unhandled error: %s", err)
        return _problem_json(500, "Internal Server Error", "An unexpected error occurred")

