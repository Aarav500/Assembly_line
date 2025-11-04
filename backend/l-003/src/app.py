import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from config import load_config
from utils.errors import register_error_handlers
from plugin_manager import PluginManager
from routes import create_api_blueprint


def create_app():
    load_dotenv()

    app = Flask(__name__)

    # Load config
    cfg = load_config()
    app.config.update(cfg)

    # CORS
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*")}})

    # Errors
    register_error_handlers(app)

    # Plugins
    manager = PluginManager(config=app.config)

    # Routes
    api_bp = create_api_blueprint(manager)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=app.config.get("HOST", "0.0.0.0"), port=int(app.config.get("PORT", 5000)), debug=app.config.get("DEBUG", False))

