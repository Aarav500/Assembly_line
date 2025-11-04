import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import subprocess
import json
import os

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        'message': 'Policy-as-Code Enforcement Service',
        'endpoints': ['/validate', '/health']
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/validate', methods=['POST'])
def validate():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    policy_type = data.get('policy_type', 'terraform')
    manifest = data.get('manifest', {})
    
    # Simulate policy validation
    violations = []
    
    # Example policy checks
    if policy_type == 'terraform':
        if manifest.get('resource', {}).get('aws_s3_bucket', {}):
            for bucket_name, bucket_config in manifest['resource']['aws_s3_bucket'].items():
                if not bucket_config.get('versioning', {}).get('enabled'):
                    violations.append(f'S3 bucket {bucket_name} must have versioning enabled')
                if bucket_config.get('acl') == 'public-read':
                    violations.append(f'S3 bucket {bucket_name} must not be publicly readable')
    
    elif policy_type == 'kubernetes':
        if manifest.get('kind') == 'Pod':
            containers = manifest.get('spec', {}).get('containers', [])
            for container in containers:
                if not container.get('securityContext', {}).get('readOnlyRootFilesystem'):
                    violations.append(f"Container {container.get('name')} should have readOnlyRootFilesystem")
                if container.get('securityContext', {}).get('privileged'):
                    violations.append(f"Container {container.get('name')} must not run as privileged")
    
    result = {
        'valid': len(violations) == 0,
        'violations': violations,
        'policy_type': policy_type
    }
    
    return jsonify(result), 200 if result['valid'] else 403

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app
