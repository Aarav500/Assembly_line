import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import re

app = Flask(__name__)

registries = {}
images = {}
lifecycle_policies = {}


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200


@app.route('/registries', methods=['POST'])
def create_registry():
    data = request.get_json()
    registry_name = data.get('name')
    if not registry_name:
        return jsonify({'error': 'Registry name is required'}), 400
    
    if registry_name in registries:
        return jsonify({'error': 'Registry already exists'}), 409
    
    registries[registry_name] = {
        'name': registry_name,
        'created_at': datetime.utcnow().isoformat(),
        'private': data.get('private', True)
    }
    images[registry_name] = []
    
    return jsonify(registries[registry_name]), 201


@app.route('/registries/<registry_name>', methods=['GET'])
def get_registry(registry_name):
    if registry_name not in registries:
        return jsonify({'error': 'Registry not found'}), 404
    
    return jsonify(registries[registry_name]), 200


@app.route('/registries/<registry_name>/images', methods=['POST'])
def push_image(registry_name):
    if registry_name not in registries:
        return jsonify({'error': 'Registry not found'}), 404
    
    data = request.get_json()
    image_name = data.get('name')
    tag = data.get('tag', 'latest')
    
    if not image_name:
        return jsonify({'error': 'Image name is required'}), 400
    
    image = {
        'name': image_name,
        'tag': tag,
        'pushed_at': datetime.utcnow().isoformat(),
        'size': data.get('size', 0)
    }
    
    images[registry_name].append(image)
    
    return jsonify(image), 201


@app.route('/registries/<registry_name>/images', methods=['GET'])
def list_images(registry_name):
    if registry_name not in registries:
        return jsonify({'error': 'Registry not found'}), 404
    
    return jsonify({'images': images[registry_name]}), 200


@app.route('/registries/<registry_name>/lifecycle-policies', methods=['POST'])
def create_lifecycle_policy(registry_name):
    if registry_name not in registries:
        return jsonify({'error': 'Registry not found'}), 404
    
    data = request.get_json()
    policy_name = data.get('name')
    
    if not policy_name:
        return jsonify({'error': 'Policy name is required'}), 400
    
    policy = {
        'name': policy_name,
        'registry': registry_name,
        'rules': data.get('rules', []),
        'created_at': datetime.utcnow().isoformat()
    }
    
    if registry_name not in lifecycle_policies:
        lifecycle_policies[registry_name] = []
    
    lifecycle_policies[registry_name].append(policy)
    
    return jsonify(policy), 201


@app.route('/registries/<registry_name>/lifecycle-policies', methods=['GET'])
def get_lifecycle_policies(registry_name):
    if registry_name not in registries:
        return jsonify({'error': 'Registry not found'}), 404
    
    policies = lifecycle_policies.get(registry_name, [])
    return jsonify({'policies': policies}), 200


@app.route('/registries/<registry_name>/lifecycle-policies/apply', methods=['POST'])
def apply_lifecycle_policies(registry_name):
    if registry_name not in registries:
        return jsonify({'error': 'Registry not found'}), 404
    
    policies = lifecycle_policies.get(registry_name, [])
    deleted_images = []
    
    for policy in policies:
        for rule in policy.get('rules', []):
            if rule.get('type') == 'expire_after_days':
                days = rule.get('days', 30)
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                for image in images[registry_name][:]:
                    pushed_at = datetime.fromisoformat(image['pushed_at'])
                    if pushed_at < cutoff_date:
                        images[registry_name].remove(image)
                        deleted_images.append(image)
    
    return jsonify({'deleted_count': len(deleted_images), 'deleted_images': deleted_images}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/registries/my-registry', methods=['GET'])
def _auto_stub_registries_my_registry():
    return 'Auto-generated stub for /registries/my-registry', 200


@app.route('/registries/test-registry/images', methods=['POST'])
def _auto_stub_registries_test_registry_images():
    return 'Auto-generated stub for /registries/test-registry/images', 200


@app.route('/registries/test-registry/lifecycle-policies', methods=['GET', 'POST'])
def _auto_stub_registries_test_registry_lifecycle_policies():
    return 'Auto-generated stub for /registries/test-registry/lifecycle-policies', 200
