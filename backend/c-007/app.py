import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, Response
from flask_smorest import Api
from ariadne import graphql_sync
from ariadne.constants import PLAYGROUND_HTML
from api.resources import blp as items_blp
from graphql_schema import schema, get_sdl, get_introspection


def create_app() -> Flask:
    app = Flask(__name__)

    # Flask-Smorest and OpenAPI configuration
    app.config["API_TITLE"] = "OpenAPI & GraphQL Demo"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/api"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/docs"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    app.config["OPENAPI_REDOC_PATH"] = "/redoc"
    app.config["OPENAPI_REDOC_URL"] = "https://cdn.jsdelivr.net/npm/redoc/bundles/redoc.standalone.js"

    api = Api(app)
    api.register_blueprint(items_blp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # GraphQL Playground
    @app.get("/graphql")
    def graphql_playground():
        return Response(PLAYGROUND_HTML, status=200, mimetype="text/html")

    # GraphQL endpoint
    @app.post("/graphql")
    def graphql_server():
        data = request.get_json() or {}
        success, result = graphql_sync(schema, data, context_value=request, debug=app.debug)
        status_code = 200 if success else 400
        return jsonify(result), status_code

    # GraphQL schema (SDL)
    @app.get("/graphql/schema.graphql")
    def graphql_schema_sdl():
        sdl = get_sdl()
        return Response(sdl, mimetype="text/plain")

    # GraphQL introspection JSON
    @app.get("/graphql/schema.json")
    def graphql_schema_json():
        data = get_introspection()
        return jsonify(data)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



@app.route('/api/hello', methods=['GET'])
def _auto_stub_api_hello():
    return 'Auto-generated stub for /api/hello', 200


@app.route('/api/hello?name=Alice', methods=['GET'])
def _auto_stub_api_hello_name_Alice():
    return 'Auto-generated stub for /api/hello?name=Alice', 200


@app.route('/api/items', methods=['GET', 'POST'])
def _auto_stub_api_items():
    return 'Auto-generated stub for /api/items', 200


@app.route('/api/users', methods=['GET'])
def _auto_stub_api_users():
    return 'Auto-generated stub for /api/users', 200
