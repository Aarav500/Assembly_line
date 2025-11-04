import os
from flask import Flask
from .config import Config
from .models import db
from .routes import api_bp
from .scheduler import Scheduler

scheduler = None


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(api_bp, url_prefix="/api")

    # Start background scheduler in main process only
    if not app.config.get("TESTING", False):
        is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        if is_reloader_child or os.environ.get("WERKZEUG_RUN_MAIN") is None:
            global scheduler
            scheduler = Scheduler(app)
            scheduler.start()

            @app.teardown_appcontext
            def shutdown_scheduler(exception=None):
                if scheduler:
                    scheduler.stop()

    return app

