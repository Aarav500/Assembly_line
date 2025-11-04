import os
from flask import Flask
from .models import db
from .routes import init_routes
from .scheduler import start_scheduler


def create_app():
    app = Flask(__name__)
    # Load config
    app.config.from_object('config.Config')

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Init db
    db.init_app(app)
    with app.app_context():
        db.create_all()

    # Register routes
    init_routes(app)

    # Start scheduler
    if app.config.get('ENABLE_SCHEDULER', True):
        start_scheduler(app)

    return app

