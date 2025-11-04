import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import time
import os

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({'message': 'Hello World', 'status': 'ok'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/api/users/<int:user_id>')
def get_user(user_id):
    return jsonify({'id': user_id, 'name': f'User {user_id}'})

@app.route('/api/slow')
def slow_endpoint():
    time.sleep(0.5)
    return jsonify({'message': 'Slow response'})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)


def create_app():
    return app


@app.route('/api/users/123', methods=['GET'])
def _auto_stub_api_users_123():
    return 'Auto-generated stub for /api/users/123', 200
