import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config

# SQLAlchemy db instance
db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # Ensure storage directories exist
    os.makedirs(app.config["STORAGE_DIR"], exist_ok=True)
    os.makedirs(os.path.join(app.config["STORAGE_DIR"], "evidence"), exist_ok=True)

    db.init_app(app)

    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()

    from .routes import bp as api_bp
    app.register_blueprint(api_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

