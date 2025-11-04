import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from config import Config
from auth import auth_bp
from payments import payments_bp
from search import search_bp
from upload import upload_bp
from rate_limit import SimpleRateLimiter, register_rate_limiter
from caching import SimpleCache, register_cache
from feature_detector import detect_features
import logging
import time

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    
    try:
        app.config.from_object(Config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Register simple in-memory cache
    try:
        cache = SimpleCache(default_timeout=app.config.get("CACHE_DEFAULT_TIMEOUT", 30))
        register_cache(app, cache)
    except Exception as e:
        logger.error(f"Failed to register cache: {e}")
        raise

    # Register global rate limiter
    try:
        limiter = SimpleRateLimiter(
            limit=app.config.get("RATE_LIMIT_REQUESTS", 100),
            window=app.config.get("RATE_LIMIT_WINDOW_SEC", 60),
        )
        register_rate_limiter(app, limiter)
    except Exception as e:
        logger.error(f"Failed to register rate limiter: {e}")
        raise

    # Register blueprints
    try:
        app.register_blueprint(auth_bp)
        app.register_blueprint(payments_bp)
        app.register_blueprint(search_bp)
        app.register_blueprint(upload_bp)
    except Exception as e:
        logger.error(f"Failed to register blueprints: {e}")
        raise

    @app.route("/")
    def index():
        try:
            return jsonify({"ok": True, "message": "Welcome to the demo app."})
        except Exception as e:
            logger.error(f"Error in index route: {e}")
            return jsonify({"ok": False, "error": "Internal server error"}), 500

    @app.route("/features")
    def features():
        try:
            report = detect_features(app)
            return jsonify(report)
        except Exception as e:
            logger.error(f"Error detecting features: {e}")
            return jsonify({"ok": False, "error": "Failed to detect features"}), 500

    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "timestamp": time.time()}

    @app.route('/ready')
    def readiness_check():
        """Readiness check endpoint"""
        return {"status": "ready"}

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"Unhandled exception: {e}")
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    try:
        app = create_app()
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
