from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Global db instance
db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    db.init_app(app)

    with app.app_context():
        from .models import init_db
        init_db()

        from .routes import bp as api_bp
        app.register_blueprint(api_bp)

    return app

