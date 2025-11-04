import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask

from .config import Config
from .extensions import db, init_scheduler
from .models import Schedule
from .routes import api_bp
from .scheduler import schedule_all, initial_state_check


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Ensure instance folder exists
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    configure_logging(app)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    init_scheduler(app)

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    # Schedule jobs after app context is ready
    with app.app_context():
        schedule_all()
        # Make sure we respect current time windows if app starts mid-window
        initial_state_check()

    @app.get("/")
    def root():
        return {"service": "time-aware-scheduled-agents", "status": "ok"}

    return app


def configure_logging(app: Flask) -> None:
    log_level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"))
    app.logger.setLevel(log_level)

    handler = RotatingFileHandler(Path(app.instance_path) / "app.log", maxBytes=1_000_000, backupCount=5)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(fmt)
    handler.setLevel(log_level)

    if not app.logger.handlers:
        app.logger.addHandler(handler)

    # Reduce noisy loggers
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

