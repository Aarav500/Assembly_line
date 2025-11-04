import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from flask_cors import CORS
from models import db
from routes import api_bp
from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        return {
            "name": "Agent Metrics & SLA Service",
            "version": "1.0.0",
            "endpoints": [
                "GET    /health",
                "POST   /agents",
                "GET    /agents",
                "GET    /agents/<agent_id>",
                "PATCH  /agents/<agent_id>",
                "PUT    /agents/<agent_id>/sla",
                "GET    /agents/<agent_id>/sla",
                "POST   /events",
                "GET    /events",
                "GET    /metrics/agents",
                "GET    /metrics/agents/<agent_id>/summary",
                "GET    /metrics/agents/<agent_id>/sla_report",
            ],
        }

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=True)

