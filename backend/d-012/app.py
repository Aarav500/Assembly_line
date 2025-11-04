import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from flask import Flask
from routes import api_bp
from models import init_db


def create_app():
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False

    # Initialize database and tables
    init_db()

    # Register API blueprint
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.get('/')
    def index():
        return {
            'name': 'Auto-rollback logic with root-cause snapshot',
            'status': 'ok'
        }

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/deploy', methods=['POST'])
def _auto_stub_deploy():
    return 'Auto-generated stub for /deploy', 200


@app.route('/incident', methods=['POST'])
def _auto_stub_incident():
    return 'Auto-generated stub for /incident', 200
