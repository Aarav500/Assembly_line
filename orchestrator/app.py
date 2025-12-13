"""
Unified API Orchestrator
Routes requests to appropriate microservices
"""

import os
import json
import requests
from pathlib import Path
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load service registry
REGISTRY_PATH = Path(__file__).parent.parent / "service_registry.json"
with open(REGISTRY_PATH) as f:
    REGISTRY = json.load(f)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "orchestrator"})

@app.route('/api/services')
def list_services():
    """List all available services"""
    all_services = []
    for category, modules in REGISTRY.items():
        for module_name, info in modules.items():
            all_services.append({
                "name": module_name,
                "category": category,
                "port": info["port"],
                "endpoints": info.get("api_endpoints", [])
            })
    return jsonify({"services": all_services, "total": len(all_services)})

@app.route('/api/<category>/<module>/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_request(category, module, endpoint):
    """Proxy requests to specific module"""

    # Find module in registry
    if category not in REGISTRY or module not in REGISTRY[category]:
        return jsonify({"error": "Module not found"}), 404

    module_info = REGISTRY[category][module]
    port = module_info["port"]

    # Build target URL
    target_url = f"http://{module}:{5000}/{endpoint}"

    # Forward request
    try:
        if request.method == 'GET':
            resp = requests.get(target_url, params=request.args, timeout=30)
        elif request.method == 'POST':
            resp = requests.post(target_url, json=request.get_json(), timeout=30)
        elif request.method == 'PUT':
            resp = requests.put(target_url, json=request.get_json(), timeout=30)
        elif request.method == 'DELETE':
            resp = requests.delete(target_url, timeout=30)

        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))

    except requests.exceptions.ConnectionError:
        return jsonify({"error": f"Module {module} is not reachable"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
