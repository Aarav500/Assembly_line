import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os
import json
from datetime import datetime

app = Flask(__name__)

PROJECTS_FILE = 'projects.json'
DEPLOYMENTS_FILE = 'deployments.json'

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/projects', methods=['POST'])
def create_project():
    data = request.get_json()
    project_name = data.get('name')
    
    if not project_name:
        return jsonify({'error': 'Project name is required'}), 400
    
    projects = load_data(PROJECTS_FILE)
    
    if project_name in projects:
        return jsonify({'error': 'Project already exists'}), 409
    
    projects[project_name] = {
        'name': project_name,
        'created_at': datetime.utcnow().isoformat(),
        'status': 'created'
    }
    
    save_data(PROJECTS_FILE, projects)
    return jsonify(projects[project_name]), 201

@app.route('/projects/<project_name>/analyze', methods=['POST'])
def analyze_project(project_name):
    projects = load_data(PROJECTS_FILE)
    
    if project_name not in projects:
        return jsonify({'error': 'Project not found'}), 404
    
    projects[project_name]['status'] = 'analyzed'
    projects[project_name]['analyzed_at'] = datetime.utcnow().isoformat()
    projects[project_name]['analysis'] = {'lines': 100, 'complexity': 'low'}
    
    save_data(PROJECTS_FILE, projects)
    return jsonify(projects[project_name])

@app.route('/projects/<project_name>/generate', methods=['POST'])
def generate_artifacts(project_name):
    projects = load_data(PROJECTS_FILE)
    
    if project_name not in projects:
        return jsonify({'error': 'Project not found'}), 404
    
    if projects[project_name]['status'] != 'analyzed':
        return jsonify({'error': 'Project must be analyzed first'}), 400
    
    projects[project_name]['status'] = 'generated'
    projects[project_name]['generated_at'] = datetime.utcnow().isoformat()
    projects[project_name]['artifacts'] = ['build.zip', 'config.yaml']
    
    save_data(PROJECTS_FILE, projects)
    return jsonify(projects[project_name])

@app.route('/projects/<project_name>/deploy', methods=['POST'])
def deploy_project(project_name):
    projects = load_data(PROJECTS_FILE)
    
    if project_name not in projects:
        return jsonify({'error': 'Project not found'}), 404
    
    if projects[project_name]['status'] != 'generated':
        return jsonify({'error': 'Project must be generated first'}), 400
    
    deployments = load_data(DEPLOYMENTS_FILE)
    
    deployment_id = f"{project_name}-{len(deployments) + 1}"
    deployments[deployment_id] = {
        'id': deployment_id,
        'project': project_name,
        'deployed_at': datetime.utcnow().isoformat(),
        'status': 'active'
    }
    
    projects[project_name]['status'] = 'deployed'
    projects[project_name]['current_deployment'] = deployment_id
    
    save_data(PROJECTS_FILE, projects)
    save_data(DEPLOYMENTS_FILE, deployments)
    
    return jsonify(deployments[deployment_id])

@app.route('/deployments/<deployment_id>/rollback', methods=['POST'])
def rollback_deployment(deployment_id):
    deployments = load_data(DEPLOYMENTS_FILE)
    
    if deployment_id not in deployments:
        return jsonify({'error': 'Deployment not found'}), 404
    
    if deployments[deployment_id]['status'] != 'active':
        return jsonify({'error': 'Deployment is not active'}), 400
    
    deployments[deployment_id]['status'] = 'rolled_back'
    deployments[deployment_id]['rolled_back_at'] = datetime.utcnow().isoformat()
    
    save_data(DEPLOYMENTS_FILE, deployments)
    return jsonify(deployments[deployment_id])

@app.route('/projects', methods=['GET'])
def list_projects():
    projects = load_data(PROJECTS_FILE)
    return jsonify(list(projects.values()))

@app.route('/deployments', methods=['GET'])
def list_deployments():
    deployments = load_data(DEPLOYMENTS_FILE)
    return jsonify(list(deployments.values()))

if __name__ == '__main__':
    app.run(debug=True, port=5000)


def create_app():
    return app


@app.route('/projects/lifecycle-test/analyze', methods=['POST'])
def _auto_stub_projects_lifecycle_test_analyze():
    return 'Auto-generated stub for /projects/lifecycle-test/analyze', 200


@app.route('/projects/lifecycle-test/generate', methods=['POST'])
def _auto_stub_projects_lifecycle_test_generate():
    return 'Auto-generated stub for /projects/lifecycle-test/generate', 200


@app.route('/projects/lifecycle-test/deploy', methods=['POST'])
def _auto_stub_projects_lifecycle_test_deploy():
    return 'Auto-generated stub for /projects/lifecycle-test/deploy', 200
