from flask import Flask
from .extensions import db
from .routes import api_bp
from config import Config

def create_app(config_object: type = Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()

    app.register_blueprint(api_bp, url_prefix="/api")

    return app

