import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'region': os.getenv('DEPLOY_REGION', 'unknown'),
        'version': '1.0.0'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/region')
def region():
    return jsonify({
        'region': os.getenv('DEPLOY_REGION', 'unknown'),
        'latency': os.getenv('REGION_LATENCY', '0')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app
