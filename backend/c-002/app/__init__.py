from flask import Flask


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = testing

    # Blueprints registered here. Endpoints are defined but intentionally
    # return 501 Not Implemented until the app is built to satisfy the
    # acceptance tests.
    from .api.health import bp as health_bp
    from .api.todos import bp as todos_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(todos_bp, url_prefix="/todos")

    return app

