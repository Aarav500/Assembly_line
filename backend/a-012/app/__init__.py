from flask import Flask, jsonify
import logging

logger = logging.getLogger(__name__)


def create_app(config: dict | None = None) -> Flask:
    try:
        app = Flask(__name__)

        # Default config
        app.config.setdefault("APP_VERSION", "0.1.0")

        if config:
            app.config.update(config)

        try:
            from .routes import bp as core_bp
            app.register_blueprint(core_bp)
        except ImportError as e:
            logger.error(f"Failed to import routes blueprint: {e}")
            raise

        # Add root endpoint and /api/data endpoint for integration tests
        @app.route('/')
        def index():
            try:
                return jsonify({"message": "Welcome to the API", "status": "running"}), 200
            except Exception as e:
                logger.error(f"Error in index route: {e}")
                return jsonify({"error": "Internal server error", "status": "error"}), 500

        @app.route('/api/data')
        def api_data():
            try:
                return jsonify({"data": "sample data", "status": "success"}), 200
            except Exception as e:
                logger.error(f"Error in api_data route: {e}")
                return jsonify({"error": "Internal server error", "status": "error"}), 500

        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled exception: {e}")
            return jsonify({"error": "Internal server error", "status": "error"}), 500

        return app
    except Exception as e:
        logger.error(f"Failed to create app: {e}")
        raise