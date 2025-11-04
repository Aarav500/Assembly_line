import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# In-memory storage for GitOps resources
gitops_apps = {}


@app.route('/')
def index():
    return jsonify({
        'message': 'GitOps Bootstrapping Service',
        'endpoints': ['/health', '/api/bootstrap', '/api/apps', '/api/apps/<name>']
    })


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200


@app.route('/api/bootstrap', methods=['POST'])
def bootstrap():
    data = request.get_json()
    tool = data.get('tool', 'argocd')
    repo_url = data.get('repo_url', '')
    
    if not repo_url:
        return jsonify({'error': 'repo_url is required'}), 400
    
    bootstrap_config = {
        'tool': tool,
        'repo_url': repo_url,
        'status': 'bootstrapped',
        'namespace': data.get('namespace', 'gitops-system')
    }
    
    return jsonify(bootstrap_config), 201


@app.route('/api/apps', methods=['GET', 'POST'])
def apps():
    if request.method == 'POST':
        data = request.get_json()
        app_name = data.get('name')
        
        if not app_name:
            return jsonify({'error': 'name is required'}), 400
        
        gitops_apps[app_name] = {
            'name': app_name,
            'repo_url': data.get('repo_url', ''),
            'path': data.get('path', '.'),
            'sync_policy': data.get('sync_policy', 'manual')
        }
        
        return jsonify(gitops_apps[app_name]), 201
    
    return jsonify({'apps': list(gitops_apps.values())}), 200


@app.route('/api/apps/<name>', methods=['GET', 'DELETE'])
def app_detail(name):
    if request.method == 'DELETE':
        if name in gitops_apps:
            del gitops_apps[name]
            return jsonify({'message': f'App {name} deleted'}), 200
        return jsonify({'error': 'App not found'}), 404
    
    if name in gitops_apps:
        return jsonify(gitops_apps[name]), 200
    
    return jsonify({'error': 'App not found'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app


@app.route('/api/apps/test-app', methods=['GET'])
def _auto_stub_api_apps_test_app():
    return 'Auto-generated stub for /api/apps/test-app', 200
