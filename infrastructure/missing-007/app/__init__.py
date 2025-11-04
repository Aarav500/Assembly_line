from flask import Flask
from .config import Config
from .extensions import socketio, redis_client
from .routes import api_bp


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Init extensions
    socketio.init_app(
        app,
        message_queue=app.config.get("MESSAGE_QUEUE_URL"),
        cors_allowed_origins=app.config.get("CORS_ALLOWED_ORIGINS"),
        async_mode=None,  # eventlet if installed
        logger=app.config.get("SOCKETIO_LOGGER", True),
        engineio_logger=app.config.get("SOCKETIO_ENGINEIO_LOGGER", False),
    )

    # Blueprints
    app.register_blueprint(api_bp)

    # Import events to register handlers
    from . import events  # noqa: F401

    @app.get("/healthz")
    def healthz():
        try:
            redis_client.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
        return {
            "status": "ok",
            "redis": redis_ok,
        }

    return app

