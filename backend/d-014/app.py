import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import yaml
import json
from datetime import datetime

app = Flask(__name__)


def validate_argocd_sync(data):
    """Validate ArgoCD sync job configuration"""
    required_fields = ['apiVersion', 'kind', 'metadata', 'spec']
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    if data.get('kind') != 'Application':
        return False, "Kind must be 'Application'"
    
    spec = data.get('spec', {})
    if 'source' not in spec or 'destination' not in spec:
        return False, "Spec must contain 'source' and 'destination'"
    
    return True, "Valid ArgoCD configuration"


def validate_flux_sync(data):
    """Validate Flux sync job configuration"""
    required_fields = ['apiVersion', 'kind', 'metadata', 'spec']
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    if data.get('kind') not in ['Kustomization', 'HelmRelease']:
        return False, "Kind must be 'Kustomization' or 'HelmRelease'"
    
    spec = data.get('spec', {})
    if 'sourceRef' not in spec:
        return False, "Spec must contain 'sourceRef'"
    
    return True, "Valid Flux configuration"


def generate_argocd_sync_job(name, repo_url, path, namespace, cluster):
    """Generate ArgoCD Application sync job"""
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": name,
            "namespace": "argocd"
        },
        "spec": {
            "project": "default",
            "source": {
                "repoURL": repo_url,
                "targetRevision": "HEAD",
                "path": path
            },
            "destination": {
                "server": cluster,
                "namespace": namespace
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True
                }
            }
        }
    }


def generate_flux_sync_job(name, repo_name, path, namespace):
    """Generate Flux Kustomization sync job"""
    return {
        "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
        "kind": "Kustomization",
        "metadata": {
            "name": name,
            "namespace": "flux-system"
        },
        "spec": {
            "interval": "5m",
            "path": path,
            "prune": True,
            "sourceRef": {
                "kind": "GitRepository",
                "name": repo_name
            },
            "targetNamespace": namespace
        }
    }


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


@app.route('/generate/argocd', methods=['POST'])
def generate_argocd():
    data = request.get_json()
    
    required = ['name', 'repoUrl', 'path', 'namespace', 'cluster']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    sync_job = generate_argocd_sync_job(
        data['name'],
        data['repoUrl'],
        data['path'],
        data['namespace'],
        data['cluster']
    )
    
    return jsonify(sync_job), 201


@app.route('/generate/flux', methods=['POST'])
def generate_flux():
    data = request.get_json()
    
    required = ['name', 'repoName', 'path', 'namespace']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    sync_job = generate_flux_sync_job(
        data['name'],
        data['repoName'],
        data['path'],
        data['namespace']
    )
    
    return jsonify(sync_job), 201


@app.route('/validate/argocd', methods=['POST'])
def validate_argocd():
    data = request.get_json()
    
    is_valid, message = validate_argocd_sync(data)
    
    if is_valid:
        return jsonify({"valid": True, "message": message}), 200
    else:
        return jsonify({"valid": False, "message": message}), 400


@app.route('/validate/flux', methods=['POST'])
def validate_flux():
    data = request.get_json()
    
    is_valid, message = validate_flux_sync(data)
    
    if is_valid:
        return jsonify({"valid": True, "message": message}), 200
    else:
        return jsonify({"valid": False, "message": message}), 400


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app
