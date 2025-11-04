from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from .models import db
from .routes import api_bp
from .services.categorizer import Categorizer
from .models import Taxonomy, Term
from .utils.text import init_stopwords
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Attach categorizer service to app context for reuse
    app.categorizer = Categorizer(default_threshold=app.config.get("DEFAULT_TAXONOMY_THRESHOLD", 1.0))

    init_stopwords()

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Server error"}), 500

    return app

