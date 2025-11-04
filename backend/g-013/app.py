import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask
from db import db, init_db
from routes.datasets import datasets_bp
from routes.code_versions import code_bp
from routes.environments import env_bp
from routes.runs import runs_bp
from routes.artifacts import artifacts_bp
from routes.audit import audit_bp


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['STORAGE_DIR'] = os.getenv('STORAGE_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), 'storage')))
    os.makedirs(app.config['STORAGE_DIR'], exist_ok=True)

    db.init_app(app)
    with app.app_context():
        init_db()

    app.register_blueprint(datasets_bp, url_prefix='/datasets')
    app.register_blueprint(code_bp, url_prefix='/code-versions')
    app.register_blueprint(env_bp, url_prefix='/environments')
    app.register_blueprint(runs_bp, url_prefix='/runs')
    app.register_blueprint(artifacts_bp, url_prefix='/artifacts')
    app.register_blueprint(audit_bp, url_prefix='/audit')

    @app.get('/')
    def health():
        return {'status': 'ok', 'message': 'Data lineage & reproducible training artifact bundles API', 'storage_dir': app.config['STORAGE_DIR']}

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8000')), debug=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/lineage', methods=['POST'])
def _auto_stub_lineage():
    return 'Auto-generated stub for /lineage', 200
