import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import json
import subprocess
import os

app = Flask(__name__)

ALLOWED_LICENSES = ['MIT', 'Apache-2.0', 'BSD-3-Clause', 'BSD-2-Clause', 'ISC']

@app.route('/')
def index():
    return jsonify({'message': 'SBOM and License Compliance API'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/sbom', methods=['GET'])
def get_sbom():
    try:
        result = subprocess.run(
            ['pip', 'list', '--format=json'],
            capture_output=True,
            text=True,
            check=True
        )
        packages = json.loads(result.stdout)
        sbom = {
            'format': 'custom-sbom-v1',
            'packages': packages
        }
        return jsonify(sbom)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/license/check', methods=['POST'])
def check_license():
    data = request.get_json()
    if not data or 'license' not in data:
        return jsonify({'error': 'license field required'}), 400
    
    license_name = data['license']
    compliant = license_name in ALLOWED_LICENSES
    
    return jsonify({
        'license': license_name,
        'compliant': compliant,
        'allowed_licenses': ALLOWED_LICENSES
    })

@app.route('/license/validate', methods=['POST'])
def validate_licenses():
    data = request.get_json()
    if not data or 'packages' not in data:
        return jsonify({'error': 'packages field required'}), 400
    
    packages = data['packages']
    violations = []
    
    for package in packages:
        license_name = package.get('license', 'Unknown')
        if license_name not in ALLOWED_LICENSES:
            violations.append({
                'package': package.get('name', 'Unknown'),
                'license': license_name
            })
    
    return jsonify({
        'compliant': len(violations) == 0,
        'violations': violations,
        'total_packages': len(packages),
        'violation_count': len(violations)
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app
