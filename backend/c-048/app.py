import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

VERSION = '2.0.0'
PREVIOUS_VERSION = '1.5.0'

UPGRADE_NOTES = {
    'version': VERSION,
    'previous_version': PREVIOUS_VERSION,
    'breaking_changes': [
        {
            'change': 'Authentication endpoint moved from /auth to /api/v2/auth',
            'impact': 'All authentication requests must use new endpoint',
            'action': 'Update client code to use /api/v2/auth'
        },
        {
            'change': 'Response format now includes metadata wrapper',
            'impact': 'API responses wrapped in {"data": ..., "meta": ...}',
            'action': 'Update response parsing to access data.result'
        }
    ],
    'new_features': [
        'Added rate limiting support',
        'Introduced API versioning',
        'Enhanced error handling with detailed messages'
    ],
    'deprecations': [
        {
            'feature': '/legacy/users endpoint',
            'removed_in': '3.0.0',
            'replacement': '/api/v2/users'
        }
    ]
}

MIGRATION_GUIDE = {
    'steps': [
        {
            'step': 1,
            'title': 'Update dependencies',
            'description': 'Run pip install -r requirements.txt to update all dependencies',
            'commands': ['pip install -r requirements.txt']
        },
        {
            'step': 2,
            'title': 'Database migrations',
            'description': 'Apply database schema changes',
            'commands': ['flask db upgrade']
        },
        {
            'step': 3,
            'title': 'Update configuration',
            'description': 'Add new environment variables: API_VERSION, RATE_LIMIT_ENABLED',
            'commands': []
        },
        {
            'step': 4,
            'title': 'Test endpoints',
            'description': 'Verify all API endpoints respond correctly',
            'commands': ['pytest tests/']
        }
    ],
    'rollback_procedure': [
        'Stop the application',
        'Restore previous version from backup',
        'Run: flask db downgrade',
        'Restart application'
    ]
}

@app.route('/')
def index():
    return jsonify({
        'message': 'Upgrade Notes and Migration Guide API',
        'version': VERSION,
        'endpoints': ['/upgrade-notes', '/migration-guide', '/health']
    })

@app.route('/upgrade-notes')
def upgrade_notes():
    return jsonify(UPGRADE_NOTES)

@app.route('/migration-guide')
def migration_guide():
    return jsonify(MIGRATION_GUIDE)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'version': VERSION})

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app
