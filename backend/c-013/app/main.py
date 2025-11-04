from __future__ import annotations

from flask import Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():  # type: ignore[no-untyped-def]
        return jsonify(status="ok"), 200

    @app.get("/")
    def index():  # type: ignore[no-untyped-def]
        return jsonify(message="Hello from Flask!"), 200

    return app

