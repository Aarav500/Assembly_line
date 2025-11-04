import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from flask_smorest import Api
from resources.users import blp as UsersBlueprint
import storage


def create_app() -> Flask:
    app = Flask(__name__)

    # OpenAPI / Swagger-UI configuration
    app.config["API_TITLE"] = "Example User API"
    app.config["API_VERSION"] = "1.0.0"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"

    # Swagger UI at /docs
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/docs"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    # ReDoc at /redoc
    app.config["OPENAPI_REDOC_PATH"] = "/redoc"
    app.config["OPENAPI_REDOC_URL"] = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"

    app.config["PROPAGATE_EXCEPTIONS"] = True

    api = Api(app)

    # Seed in-memory data for examples
    storage.seed()

    # Register blueprints
    api.register_blueprint(UsersBlueprint)

    @app.get("/")
    def index():
        return {
            "message": "Welcome to Example User API",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "redoc": "/redoc",
        }

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

