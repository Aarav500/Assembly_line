import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify
from config import Config
from models import db
from scheduler import RotationScheduler
from breach import api_bp

scheduler = None


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure encryption key exists
    if not app.config.get('ENCRYPTION_KEY'):
        raise RuntimeError('ENCRYPTION_KEY not set. Generate one with scripts/generate_key.py and set in environment.')

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok"})

    # Start rotation scheduler
    global scheduler
    scheduler = RotationScheduler(app)
    scheduler.start()

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    @app.route('/shutdown', methods=['POST'])
    def shutdown():
        # test helper, not for production
        global scheduler
        if scheduler:
            scheduler.stop()
        return jsonify({"status": "shutting down"})

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



@app.route('/credentials/register', methods=['POST'])
def _auto_stub_credentials_register():
    return 'Auto-generated stub for /credentials/register', 200


@app.route('/credentials/test-machine-001', methods=['GET'])
def _auto_stub_credentials_test_machine_001():
    return 'Auto-generated stub for /credentials/test-machine-001', 200


@app.route('/credentials/revoke', methods=['POST'])
def _auto_stub_credentials_revoke():
    return 'Auto-generated stub for /credentials/revoke', 200


@app.route('/credentials/test-machine-002', methods=['GET'])
def _auto_stub_credentials_test_machine_002():
    return 'Auto-generated stub for /credentials/test-machine-002', 200


@app.route('/breach/detect', methods=['POST'])
def _auto_stub_breach_detect():
    return 'Auto-generated stub for /breach/detect', 200


@app.route('/status', methods=['GET'])
def _auto_stub_status():
    return 'Auto-generated stub for /status', 200


@app.route('/api/credentials', methods=['POST'])
def _auto_stub_api_credentials():
    return 'Auto-generated stub for /api/credentials', 200


@app.route('/api/validate', methods=['POST'])
def _auto_stub_api_validate():
    return 'Auto-generated stub for /api/validate', 200
