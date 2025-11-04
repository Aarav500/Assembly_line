import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
import os

app = Flask(__name__)

ENV = os.getenv('ENVIRONMENT', 'dev')

POLICIES = {
    'dev': {
        'max_requests_per_minute': 1000,
        'debug': True,
        'require_auth': False,
        'log_level': 'DEBUG'
    },
    'stage': {
        'max_requests_per_minute': 500,
        'debug': True,
        'require_auth': True,
        'log_level': 'INFO'
    },
    'prod': {
        'max_requests_per_minute': 100,
        'debug': False,
        'require_auth': True,
        'log_level': 'WARNING'
    }
}

def get_policy():
    return POLICIES.get(ENV, POLICIES['dev'])

@app.route('/')
def index():
    return jsonify({
        'message': 'Hello World',
        'environment': ENV
    })

@app.route('/policy')
def policy():
    return jsonify({
        'environment': ENV,
        'policy': get_policy()
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'environment': ENV})

if __name__ == '__main__':
    policy = get_policy()
    app.run(debug=policy['debug'], host='0.0.0.0', port=5000)



def create_app():
    return app
