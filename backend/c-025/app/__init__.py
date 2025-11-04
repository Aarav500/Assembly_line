import os
from flask import Flask
from .config import Config
from .search import create_search_client
from .routes import api_bp
from . import cli as cli_commands

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    # Init search client
    app.extensions = getattr(app, "extensions", {})
    app.extensions["search"] = create_search_client(app.config)

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    # Register CLI commands
    cli_commands.init_app(app)

    @app.route("/healthz")
    def healthz():
        search = app.extensions["search"]
        ok = False
        try:
            ok = search.ping()
        except Exception:
            ok = False
        return ({"status": "ok" if ok else "degraded"}, 200 if ok else 503)

    return app

