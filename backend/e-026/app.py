import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from config import AppConfig
from routes.suggestions import suggestions_bp
from routes.alerts import alerts_bp
from routes.resources import resources_bp
from routes.ingest import ingest_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(AppConfig())

    app.register_blueprint(suggestions_bp, url_prefix="/api/v1")
    app.register_blueprint(alerts_bp, url_prefix="/api/v1")
    app.register_blueprint(resources_bp, url_prefix="/api/v1")
    app.register_blueprint(ingest_bp, url_prefix="/api/v1")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "infra-cost-optimizer"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080)



@app.route('/api/resources', methods=['GET'])
def _auto_stub_api_resources():
    return 'Auto-generated stub for /api/resources', 200


@app.route('/api/suggestions', methods=['GET'])
def _auto_stub_api_suggestions():
    return 'Auto-generated stub for /api/suggestions', 200


@app.route('/api/alerts', methods=['GET'])
def _auto_stub_api_alerts():
    return 'Auto-generated stub for /api/alerts', 200


@app.route('/api/resources/i-001/optimize', methods=['POST'])
def _auto_stub_api_resources_i_001_optimize():
    return 'Auto-generated stub for /api/resources/i-001/optimize', 200


@app.route('/api/resources/nonexistent/optimize', methods=['POST'])
def _auto_stub_api_resources_nonexistent_optimize():
    return 'Auto-generated stub for /api/resources/nonexistent/optimize', 200
