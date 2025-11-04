import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from config import Config
from database import db
from routes import api_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    with app.app_context():
        # Import models to register metadata
        from models import Team, Project, ModelDef, LedgerEntry  # noqa: F401
        db.create_all()

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)



@app.route('/usage', methods=['POST'])
def _auto_stub_usage():
    return 'Auto-generated stub for /usage', 200


@app.route('/usage?project=project-a', methods=['GET'])
def _auto_stub_usage_project_project_a():
    return 'Auto-generated stub for /usage?project=project-a', 200


@app.route('/summary', methods=['GET'])
def _auto_stub_summary():
    return 'Auto-generated stub for /summary', 200
