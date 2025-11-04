import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'nightly-integration-load-test'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/trigger-integration-test', methods=['POST'])
def trigger_integration_test():
    return jsonify({
        'job': 'integration-test',
        'status': 'triggered',
        'timestamp': datetime.utcnow().isoformat()
    }), 202

@app.route('/trigger-load-test', methods=['POST'])
def trigger_load_test():
    return jsonify({
        'job': 'load-test',
        'status': 'triggered',
        'timestamp': datetime.utcnow().isoformat()
    }), 202

@app.route('/jobs/status')
def jobs_status():
    return jsonify({
        'integration_tests': 'idle',
        'load_tests': 'idle',
        'last_run': None
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)



def create_app():
    return app
