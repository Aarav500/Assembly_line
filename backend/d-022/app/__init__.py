from flask import Flask
from .routes import routes_bp
from .webhook import webhook_bp


def create_app():
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(routes_bp)
    app.register_blueprint(webhook_bp, url_prefix="/webhook")

    return app

