import os
from flask import Flask
from dotenv import load_dotenv

from .routes import api_bp, web_bp


def create_app():
    load_dotenv()

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(web_bp)
    return app

