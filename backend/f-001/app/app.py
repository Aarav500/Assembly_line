import os

from flask import Flask, jsonify

from instrumentation import instrument_flask_app


def create_app():
    app = Flask(__name__)

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.route("/")
    def index():
        return jsonify({"message": "Hello, World!"})

    # Insert auto-instrumentation for this app instance (metrics + tracing + logging)
    instrument_flask_app(app)

    return app


if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host=host, port=port, debug=debug)

