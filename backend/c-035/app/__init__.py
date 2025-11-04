from flask import Flask, jsonify


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    # Default configuration
    app.config.update({
        "PROJECT_NAME": "Auto-Generated Dev CLI Demo",
        "ENV": "development",
        "DEBUG": True,
    })
    if config:
        app.config.update(config)

    @app.get("/")
    def index():
        return jsonify({"message": "Hello from Flask app", "project": app.config.get("PROJECT_NAME")})

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    return app

