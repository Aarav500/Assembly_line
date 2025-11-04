from flask import Flask
from .config import Config
from .versioning import versioning_before_request, versioning_after_request
from .errors import register_error_handlers
from .resources.v1.users import bp as users_v1_bp
from .resources.v2.users import bp as users_v2_bp
from .resources.default import bp as default_api_bp
from .resources.common import bp as common_bp


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    # Blueprints for explicit versioned paths
    app.register_blueprint(users_v1_bp)
    app.register_blueprint(users_v2_bp)

    # Negotiated/default routes
    app.register_blueprint(default_api_bp)

    # Common endpoints (health, docs)
    app.register_blueprint(common_bp)

    # Versioning middleware
    app.before_request(versioning_before_request)
    app.after_request(versioning_after_request)

    # Error handling
    register_error_handlers(app)

    return app

