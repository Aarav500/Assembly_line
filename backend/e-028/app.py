import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from datetime import datetime
import hashlib
import json

app = Flask(__name__)

artifacts = {}
modules = {}


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/artifacts', methods=['POST'])
def create_artifact():
    data = request.get_json()
    name = data.get('name')
    content = data.get('content')
    
    if not name or not content:
        return jsonify({'error': 'name and content required'}), 400
    
    artifact_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    artifact_id = f"{name}:{artifact_hash[:12]}"
    
    if artifact_id in artifacts:
        return jsonify({'error': 'artifact already exists', 'id': artifact_id}), 409
    
    artifacts[artifact_id] = {
        'id': artifact_id,
        'name': name,
        'content': content,
        'hash': artifact_hash,
        'created_at': datetime.utcnow().isoformat()
    }
    
    return jsonify(artifacts[artifact_id]), 201


@app.route('/artifacts/<artifact_id>', methods=['GET'])
def get_artifact(artifact_id):
    if artifact_id not in artifacts:
        return jsonify({'error': 'artifact not found'}), 404
    return jsonify(artifacts[artifact_id])


@app.route('/artifacts', methods=['GET'])
def list_artifacts():
    return jsonify({'artifacts': list(artifacts.values())})


@app.route('/modules', methods=['POST'])
def create_module():
    data = request.get_json()
    name = data.get('name')
    version = data.get('version')
    source = data.get('source')
    
    if not name or not version or not source:
        return jsonify({'error': 'name, version, and source required'}), 400
    
    module_id = f"{name}@{version}"
    
    if module_id in modules:
        return jsonify({'error': 'module version already exists', 'id': module_id}), 409
    
    modules[module_id] = {
        'id': module_id,
        'name': name,
        'version': version,
        'source': source,
        'created_at': datetime.utcnow().isoformat()
    }
    
    return jsonify(modules[module_id]), 201


@app.route('/modules/<module_id>', methods=['GET'])
def get_module(module_id):
    if module_id not in modules:
        return jsonify({'error': 'module not found'}), 404
    return jsonify(modules[module_id])


@app.route('/modules', methods=['GET'])
def list_modules():
    return jsonify({'modules': list(modules.values())})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/modules/vpc-module@1.0.0', methods=['GET'])
def _auto_stub_modules_vpc_module_1_0_0():
    return 'Auto-generated stub for /modules/vpc-module@1.0.0', 200


@app.route('/healthz', methods=['GET'])
def _auto_stub_healthz():
    return 'Auto-generated stub for /healthz', 200


@app.route('/artifacts/ami/tags/v1.0.0', methods=['GET'])
def _auto_stub_artifacts_ami_tags_v1_0_0():
    return 'Auto-generated stub for /artifacts/ami/tags/v1.0.0', 200


@app.route('/modules/testmod/1.2.3', methods=['GET', 'POST'])
def _auto_stub_modules_testmod_1_2_3():
    return 'Auto-generated stub for /modules/testmod/1.2.3', 200
