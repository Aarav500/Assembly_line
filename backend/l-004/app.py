import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify

from config import Config
from extensions import db
from tenancy import tenancy_before_request, tenancy_teardown_request
from routes.tenants import bp as tenants_bp
from routes.usage import bp as usage_bp
from routes.billing import bp as billing_bp
from cli import seed as seed_command


def create_app(config_object: str | None = None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    db.init_app(app)

    with app.app_context():
        # Create tables
        db.create_all()

    app.before_request(tenancy_before_request)
    app.teardown_request(tenancy_teardown_request)

    # Blueprints
    app.register_blueprint(tenants_bp)
    app.register_blueprint(usage_bp)
    app.register_blueprint(billing_bp)

    # CLI
    app.cli.add_command(seed_command)

    @app.get('/')
    def health():
        return jsonify({'ok': True, 'service': 'multi-tenant-demo'})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'not_found'}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'error': 'server_error'}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))



@app.route('/tenants', methods=['POST'])
def _auto_stub_tenants():
    return 'Auto-generated stub for /tenants', 200
