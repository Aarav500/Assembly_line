import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecretMasker(logging.Filter):
    def __init__(self):
        super().__init__()
        self.secrets = set()
        for key, value in os.environ.items():
            if 'SECRET' in key or 'PASSWORD' in key or 'TOKEN' in key or 'API_KEY' in key:
                if value:
                    self.secrets.add(value)
    
    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            for secret in self.secrets:
                if secret in msg:
                    msg = msg.replace(secret, '***MASKED***')
            record.msg = msg
        return True

masker = SecretMasker()
logger.addFilter(masker)

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': 'CI Secrets Acceleration API'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/secret', methods=['POST'])
def handle_secret():
    data = request.get_json()
    secret_key = data.get('key', '')
    secret_value = data.get('value', '')
    
    logger.info(f"Processing secret with key: {secret_key}")
    logger.info(f"Secret value received: {secret_value}")
    
    return jsonify({
        'status': 'success',
        'message': 'Secret processed',
        'key': secret_key
    }), 200

@app.route('/validate', methods=['POST'])
def validate_secret():
    data = request.get_json()
    token = data.get('token', '')
    
    expected_token = os.environ.get('API_TOKEN', 'default-secret-token')
    
    if token == expected_token:
        logger.info(f"Valid token provided: {token}")
        return jsonify({'valid': True}), 200
    else:
        logger.warning(f"Invalid token attempt: {token}")
        return jsonify({'valid': False}), 401

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)



def create_app():
    return app
