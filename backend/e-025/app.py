import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from datetime import datetime
import uuid

app = Flask(__name__)

environments = {}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

@app.route('/environments', methods=['GET'])
def list_environments():
    return jsonify({"environments": list(environments.values())})

@app.route('/environments', methods=['POST'])
def create_environment():
    data = request.get_json()
    
    if not data or 'name' not in data or 'type' not in data:
        return jsonify({"error": "Missing required fields: name, type"}), 400
    
    env_type = data['type']
    if env_type not in ['dev', 'stage', 'prod']:
        return jsonify({"error": "Invalid type. Must be dev, stage, or prod"}), 400
    
    env_id = str(uuid.uuid4())
    environment = {
        "id": env_id,
        "name": data['name'],
        "type": env_type,
        "status": "provisioning",
        "created_at": datetime.utcnow().isoformat(),
        "team": data.get('team', 'default')
    }
    
    environments[env_id] = environment
    return jsonify(environment), 201

@app.route('/environments/<env_id>', methods=['GET'])
def get_environment(env_id):
    environment = environments.get(env_id)
    if not environment:
        return jsonify({"error": "Environment not found"}), 404
    return jsonify(environment)

@app.route('/environments/<env_id>', methods=['DELETE'])
def delete_environment(env_id):
    if env_id not in environments:
        return jsonify({"error": "Environment not found"}), 404
    
    del environments[env_id]
    return jsonify({"message": "Environment deleted"}), 200

@app.route('/environments/<env_id>/status', methods=['PATCH'])
def update_status(env_id):
    if env_id not in environments:
        return jsonify({"error": "Environment not found"}), 404
    
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({"error": "Missing status field"}), 400
    
    valid_statuses = ['provisioning', 'active', 'failed', 'terminated']
    if data['status'] not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of {valid_statuses}"}), 400
    
    environments[env_id]['status'] = data['status']
    return jsonify(environments[env_id])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app
