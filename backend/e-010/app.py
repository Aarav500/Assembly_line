import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os
import time

app = Flask(__name__)

# Health endpoints for service mesh probes
@app.route('/health/live', methods=['GET'])
def liveness():
    return jsonify({"status": "alive"}), 200

@app.route('/health/ready', methods=['GET'])
def readiness():
    return jsonify({"status": "ready"}), 200

# Metrics endpoint for observability
@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify({
        "requests_total": 100,
        "request_duration_seconds": 0.05,
        "errors_total": 2
    }), 200

# Main API endpoint
@app.route('/api/v1/service', methods=['GET'])
def service():
    trace_id = request.headers.get('X-Request-Id', 'none')
    service_name = os.getenv('SERVICE_NAME', 'flask-service')
    
    return jsonify({
        "service": service_name,
        "trace_id": trace_id,
        "timestamp": time.time(),
        "mesh_headers": {
            "x-request-id": request.headers.get('X-Request-Id'),
            "x-b3-traceid": request.headers.get('X-B3-TraceId'),
            "x-b3-spanid": request.headers.get('X-B3-SpanId')
        }
    }), 200

# Traffic control test endpoint
@app.route('/api/v1/canary', methods=['GET'])
def canary():
    version = os.getenv('APP_VERSION', 'v1')
    return jsonify({
        "version": version,
        "message": f"This is version {version}"
    }), 200

# Circuit breaker test endpoint
@app.route('/api/v1/slow', methods=['GET'])
def slow_endpoint():
    delay = float(request.args.get('delay', 0.1))
    time.sleep(delay)
    return jsonify({"message": "slow response", "delay": delay}), 200

@app.route('/api/v1/error', methods=['GET'])
def error_endpoint():
    return jsonify({"error": "simulated error"}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)



def create_app():
    return app
