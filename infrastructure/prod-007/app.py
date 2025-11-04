import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from typing import Any, Dict
from flask import Flask, jsonify, request, g
from werkzeug.exceptions import HTTPException

from models.schemas import UserCreate, PostCreate, SearchQuery, DNSLookupRequest
from security.sanitization import (
    sanitize_plain_text,
    sanitize_for_like_query,
    safe_run_command,
)
from db import (
    get_db,
    close_db,
    init_db,
    create_user,
    create_post,
    search_posts,
    get_user_by_username,
)


def create_app() -> Flask:
    app = Flask(__name__)

    # Basic secure defaults
    app.config.update(
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,  # 1 MiB max request size
        JSON_AS_ASCII=False,
        JSON_SORT_KEYS=False,
        DATABASE=os.environ.get("APP_DATABASE", os.path.join(os.getcwd(), "app.db")),
        ENV=os.environ.get("FLASK_ENV", "production"),
    )

    # Initialize DB on startup
    with app.app_context():
        init_db()

    @app.teardown_appcontext
    def teardown_db(exception: Exception | None) -> None:
        close_db(exception)

    @app.after_request
    def set_security_headers(resp):
        # Content Security Policy (mostly relevant for HTML responses)
        resp.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        return resp

    @app.errorhandler(HTTPException)
    def handle_http_error(e: HTTPException):
        payload: Dict[str, Any] = {
            "error": {
                "type": e.__class__.__name__,
                "message": sanitize_plain_text(e.description) if e.description else "",
                "status": e.code,
            }
        }
        return jsonify(payload), e.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(e: Exception):
        # Do not leak internals
        payload = {"error": {"type": "ServerError", "message": "An unexpected error occurred.", "status": 500}}
        return jsonify(payload), 500

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/users")
    def users_create():
        if not request.is_json:
            return jsonify({"error": {"message": "Content-Type must be application/json"}}), 415
        try:
            data = UserCreate.model_validate(request.get_json(silent=True) or {})
        except Exception as ex:
            return jsonify({"error": {"message": "Invalid input", "details": str(ex)}}), 422

        db = get_db()
        try:
            user_id = create_user(db, username=data.username, email=data.email, bio=data.bio or "")
        except Exception as ex:
            # Likely constraint violation (e.g., unique)
            return jsonify({"error": {"message": "Could not create user"}}), 400

        return jsonify({
            "id": user_id,
            "username": data.username,
            "email": data.email,
            "bio": data.bio or "",
        }), 201

    @app.post("/posts")
    def posts_create():
        if not request.is_json:
            return jsonify({"error": {"message": "Content-Type must be application/json"}}), 415
        try:
            data = PostCreate.model_validate(request.get_json(silent=True) or {})
        except Exception as ex:
            return jsonify({"error": {"message": "Invalid input", "details": str(ex)}}), 422

        db = get_db()
        # Ensure user exists
        user = get_user_by_username(db, data.username)
        if not user:
            return jsonify({"error": {"message": "User not found"}}), 404

        post_id = create_post(db, user_id=user["id"], title=data.title, content=data.content)
        return jsonify({
            "id": post_id,
            "user_id": user["id"],
            "title": data.title,
            "content": data.content,
        }), 201

    @app.get("/search")
    def search():
        # Validate query params using Pydantic
        try:
            data = SearchQuery.model_validate(dict(request.args))
        except Exception as ex:
            return jsonify({"error": {"message": "Invalid query", "details": str(ex)}}), 422

        pattern, esc = sanitize_for_like_query(data.q)
        db = get_db()
        rows = search_posts(db, pattern, esc)
        return jsonify({"results": rows})

    @app.get("/utils/dns-lookup")
    def dns_lookup():
        # Demonstrates safe subprocess usage with strict validation to prevent command injection
        try:
            data = DNSLookupRequest.model_validate(dict(request.args))
        except Exception as ex:
            return jsonify({"error": {"message": "Invalid host", "details": str(ex)}}), 422

        try:
            # Using nslookup as read-only example; shell=False avoids shell injection
            result = safe_run_command(["nslookup", data.host])
        except Exception:
            return jsonify({"error": {"message": "Lookup failed"}}), 400

        return jsonify({"host": data.host, "output": result})

    return app


app = create_app()

if __name__ == "__main__":
    # Use a production-grade server in real deployments
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

