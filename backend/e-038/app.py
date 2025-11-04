import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os
import json

app = Flask(__name__)

ENVIRONMENTS = ['dev', 'staging', 'prod']
IAM_ROLES = {
    'dev': {
        'role_arn': 'arn:aws:iam::123456789012:role/DevFederatedRole',
        'trust_policy': 'oidc-provider-dev'
    },
    'staging': {
        'role_arn': 'arn:aws:iam::123456789012:role/StagingFederatedRole',
        'trust_policy': 'oidc-provider-staging'
    },
    'prod': {
        'role_arn': 'arn:aws:iam::123456789012:role/ProdFederatedRole',
        'trust_policy': 'oidc-provider-prod'
    }
}

@app.route('/')
def index():
    return jsonify({'message': 'Identity Federation & IAM Role Provisioning Service'})

@app.route('/roles', methods=['GET'])
def get_roles():
    return jsonify({'environments': ENVIRONMENTS, 'roles': IAM_ROLES})

@app.route('/roles/<environment>', methods=['GET'])
def get_role(environment):
    if environment not in IAM_ROLES:
        return jsonify({'error': 'Environment not found'}), 404
    return jsonify({'environment': environment, 'role': IAM_ROLES[environment]})

@app.route('/federate', methods=['POST'])
def federate():
    data = request.get_json()
    environment = data.get('environment')
    user_id = data.get('user_id')
    
    if not environment or not user_id:
        return jsonify({'error': 'Missing environment or user_id'}), 400
    
    if environment not in IAM_ROLES:
        return jsonify({'error': 'Invalid environment'}), 404
    
    role = IAM_ROLES[environment]
    return jsonify({
        'status': 'success',
        'user_id': user_id,
        'environment': environment,
        'assumed_role': role['role_arn'],
        'trust_provider': role['trust_policy']
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/roles/dev', methods=['GET'])
def _auto_stub_roles_dev():
    return 'Auto-generated stub for /roles/dev', 200
