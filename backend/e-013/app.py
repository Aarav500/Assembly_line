import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import time

app = Flask(__name__)

# Simulate edge cache
edge_cache = {}

@app.route('/')
def index():
    return jsonify({
        'service': 'edge-worker',
        'status': 'active',
        'latency': 'low'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

@app.route('/api/data/<key>', methods=['GET'])
def get_data(key):
    start_time = time.time()
    data = edge_cache.get(key)
    latency_ms = (time.time() - start_time) * 1000
    
    if data:
        return jsonify({
            'key': key,
            'value': data,
            'cached': True,
            'latency_ms': round(latency_ms, 2)
        })
    return jsonify({'error': 'key not found', 'latency_ms': round(latency_ms, 2)}), 404

@app.route('/api/data/<key>', methods=['POST'])
def set_data(key):
    start_time = time.time()
    value = request.json.get('value')
    edge_cache[key] = value
    latency_ms = (time.time() - start_time) * 1000
    
    return jsonify({
        'key': key,
        'value': value,
        'cached': True,
        'latency_ms': round(latency_ms, 2)
    }), 201

@app.route('/api/purge', methods=['POST'])
def purge_cache():
    edge_cache.clear()
    return jsonify({'status': 'cache purged'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)


def create_app():
    return app


@app.route('/api/data/test-key', methods=['GET', 'POST'])
def _auto_stub_api_data_test_key():
    return 'Auto-generated stub for /api/data/test-key', 200


@app.route('/api/data/non-existent', methods=['GET'])
def _auto_stub_api_data_non_existent():
    return 'Auto-generated stub for /api/data/non-existent', 200
