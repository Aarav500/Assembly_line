import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

artifacts = {}
preview_resources = {}
cleanup_interval = 60


def cleanup_task():
    while True:
        time.sleep(cleanup_interval)
        current_time = datetime.now()
        
        expired_artifacts = [aid for aid, data in artifacts.items() 
                            if data.get('expires_at') and data['expires_at'] < current_time]
        for aid in expired_artifacts:
            del artifacts[aid]
        
        expired_resources = [rid for rid, data in preview_resources.items() 
                            if data.get('expires_at') and data['expires_at'] < current_time]
        for rid in expired_resources:
            del preview_resources[rid]


cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200


@app.route('/artifacts', methods=['POST'])
def create_artifact():
    data = request.get_json()
    artifact_id = data.get('id')
    ttl_minutes = data.get('ttl', 60)
    
    artifacts[artifact_id] = {
        'id': artifact_id,
        'data': data.get('data'),
        'created_at': datetime.now(),
        'expires_at': datetime.now() + timedelta(minutes=ttl_minutes)
    }
    
    return jsonify({'id': artifact_id, 'status': 'created'}), 201


@app.route('/artifacts/<artifact_id>', methods=['GET'])
def get_artifact(artifact_id):
    if artifact_id in artifacts:
        return jsonify(artifacts[artifact_id]), 200
    return jsonify({'error': 'Artifact not found'}), 404


@app.route('/artifacts/<artifact_id>', methods=['DELETE'])
def delete_artifact(artifact_id):
    if artifact_id in artifacts:
        del artifacts[artifact_id]
        return jsonify({'status': 'deleted'}), 200
    return jsonify({'error': 'Artifact not found'}), 404


@app.route('/preview-resources', methods=['POST'])
def create_preview_resource():
    data = request.get_json()
    resource_id = data.get('id')
    ttl_minutes = data.get('ttl', 60)
    
    preview_resources[resource_id] = {
        'id': resource_id,
        'pr_number': data.get('pr_number'),
        'created_at': datetime.now(),
        'expires_at': datetime.now() + timedelta(minutes=ttl_minutes)
    }
    
    return jsonify({'id': resource_id, 'status': 'created'}), 201


@app.route('/preview-resources/<resource_id>', methods=['GET'])
def get_preview_resource(resource_id):
    if resource_id in preview_resources:
        return jsonify(preview_resources[resource_id]), 200
    return jsonify({'error': 'Resource not found'}), 404


@app.route('/preview-resources/<resource_id>', methods=['DELETE'])
def delete_preview_resource(resource_id):
    if resource_id in preview_resources:
        del preview_resources[resource_id]
        return jsonify({'status': 'deleted'}), 200
    return jsonify({'error': 'Resource not found'}), 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/artifacts/test-artifact-1', methods=['GET'])
def _auto_stub_artifacts_test_artifact_1():
    return 'Auto-generated stub for /artifacts/test-artifact-1', 200


@app.route('/preview-resources/preview-123', methods=['DELETE', 'GET'])
def _auto_stub_preview_resources_preview_123():
    return 'Auto-generated stub for /preview-resources/preview-123', 200
