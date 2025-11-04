from flask import Flask, jsonify
from . import rbac
from .routes import bp as routes_bp


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
        # Override or extend RBAC config here if needed.
    )

    # Register global error handlers (optional)
    @app.errorhandler(403)
    def forbidden(_):
        return jsonify({"error": "forbidden", "reason": "RBAC: insufficient role"}), 403

    rbac.init_app(app)
    app.register_blueprint(routes_bp)

    @app.get("/public/ping")
    def ping():
        return jsonify({"status": "ok"})

    return app

