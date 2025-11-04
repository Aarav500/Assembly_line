import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

OPA_URL = os.getenv('OPA_URL', 'http://localhost:8181')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/validate', methods=['POST'])
def validate():
    """Validate infrastructure configuration against OPA policies"""
    try:
        config = request.get_json()
        if not config:
            return jsonify({'error': 'No configuration provided'}), 400
        
        # Send to OPA for policy evaluation
        opa_response = requests.post(
            f'{OPA_URL}/v1/data/infrastructure/deny',
            json={'input': config},
            timeout=5
        )
        
        if opa_response.status_code != 200:
            return jsonify({'error': 'OPA service error'}), 502
        
        result = opa_response.json()
        violations = result.get('result', [])
        
        if violations:
            return jsonify({
                'allowed': False,
                'violations': violations
            }), 403
        
        return jsonify({
            'allowed': True,
            'violations': []
        }), 200
        
    except requests.exceptions.RequestException:
        return jsonify({'error': 'Cannot connect to OPA service'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/policies', methods=['GET'])
def list_policies():
    """List available OPA policies"""
    try:
        opa_response = requests.get(
            f'{OPA_URL}/v1/policies',
            timeout=5
        )
        
        if opa_response.status_code != 200:
            return jsonify({'error': 'OPA service error'}), 502
        
        return jsonify(opa_response.json()), 200
        
    except requests.exceptions.RequestException:
        return jsonify({'error': 'Cannot connect to OPA service'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)



def create_app():
    return app
