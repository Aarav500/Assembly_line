import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
import os

app = Flask(__name__)

VERSION = os.getenv('APP_VERSION', 'v1')
DEPLOYMENT_TYPE = os.getenv('DEPLOYMENT_TYPE', 'blue')

@app.route('/')
def index():
    return jsonify({
        'status': 'healthy',
        'version': VERSION,
        'deployment': DEPLOYMENT_TYPE
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'deployment': DEPLOYMENT_TYPE}), 200

@app.route('/version')
def version():
    return jsonify({
        'version': VERSION,
        'deployment': DEPLOYMENT_TYPE
    })

@app.route('/traffic')
def traffic():
    return jsonify({
        'deployment': DEPLOYMENT_TYPE,
        'version': VERSION,
        'message': f'Traffic routed to {DEPLOYMENT_TYPE} deployment'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)



def create_app():
    return app
