import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from blueprints.api import api_bp
from blueprints.admin import admin_bp

app = Flask(__name__)
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/admin')

@app.route('/')
def index():
    return jsonify({
        'message': 'Flask Project with Blueprints',
        'blueprints': ['api', 'admin'],
        'recommended_upgrades': [
            'Add database support (SQLAlchemy)',
            'Implement authentication (Flask-Login)',
            'Add API documentation (Flask-RESTX)',
            'Set up logging and monitoring',
            'Add rate limiting (Flask-Limiter)'
        ]
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(debug=True)


def create_app():
    return app


@app.route('/api/v1/blueprints', methods=['GET'])
def _auto_stub_api_v1_blueprints():
    return 'Auto-generated stub for /api/v1/blueprints', 200


@app.route('/api/v1/suggest', methods=['POST'])
def _auto_stub_api_v1_suggest():
    return 'Auto-generated stub for /api/v1/suggest', 200
