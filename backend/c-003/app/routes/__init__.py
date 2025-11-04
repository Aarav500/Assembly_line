from .health import bp as health_bp
from .example import bp as api_bp


def register_blueprints(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    return app

