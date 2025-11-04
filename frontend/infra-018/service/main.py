from flask import Flask
from .config import Config
from .db import init_engine, init_session, db_session
from .routes.track import bp as track_bp
from .routes.metrics import bp as metrics_bp
from .routes.health import bp as health_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # Init DB
    engine = init_engine(app.config["DATABASE_URL"], pool_size=10, max_overflow=20)
    init_session(engine)

    # Blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(track_bp, url_prefix="/api")
    app.register_blueprint(metrics_bp, url_prefix="/api")

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000)

