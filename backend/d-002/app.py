import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os

app = Flask(__name__)

@app.route('/')
def index():
    env = os.getenv('ENVIRONMENT', 'development')
    return jsonify({
        'message': 'PR Preview Environment',
        'environment': env,
        'status': 'running'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/api/data', methods=['GET', 'POST'])
def data():
    if request.method == 'POST':
        data = request.get_json()
        return jsonify({'received': data, 'method': 'POST'}), 201
    return jsonify({'data': [1, 2, 3], 'method': 'GET'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)



def create_app():
    return app
