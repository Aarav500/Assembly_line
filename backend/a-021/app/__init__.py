import os
from flask import Flask
from .api import api_bp


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    # Basic configuration
    app.config.update(
        JSON_SORT_KEYS=False,
        SUGGESTION_TOP_K=int(os.environ.get("SUGGESTION_TOP_K", "3")),
        BLUEPRINTS_PATH=os.environ.get(
            "BLUEPRINTS_PATH",
            os.path.join(os.path.dirname(__file__), "data", "blueprints.json"),
        ),
    )

    if test_config:
        app.config.update(test_config)

    app.register_blueprint(api_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

