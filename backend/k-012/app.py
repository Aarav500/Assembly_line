import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from config import Config
from models import db
from routes import api


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(api)

    @app.route('/health')
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=True)



@app.route('/agents', methods=['POST'])
def _auto_stub_agents():
    return 'Auto-generated stub for /agents', 200


@app.route('/api/orgs', methods=['POST'])
def _auto_stub_api_orgs():
    return 'Auto-generated stub for /api/orgs', 200


@app.route('/api/resources', methods=['GET', 'POST'])
def _auto_stub_api_resources():
    return 'Auto-generated stub for /api/resources', 200


@app.route('/api/agents', methods=['POST'])
def _auto_stub_api_agents():
    return 'Auto-generated stub for /api/agents', 200
