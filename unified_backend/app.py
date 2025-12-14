"""
UNIFIED BACKEND SERVICE
Dynamically loads and routes to all 437 modules
Save as: D:/Assemblyline/unified_app/unified_backend/app.py
"""
import os
import sys
import json
import importlib.util
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load service registry
REGISTRY_PATH = Path(__file__).parent.parent / "service_registry.json"
SERVICE_REGISTRY = {}

try:
    with open(REGISTRY_PATH) as f:
        SERVICE_REGISTRY = json.load(f)
    print(f"✓ Loaded {len(SERVICE_REGISTRY)} services from registry")
except FileNotFoundError:
    print("⚠ Warning: service_registry.json not found")
except Exception as e:
    print(f"⚠ Error loading registry: {e}")

# Cache for loaded modules
MODULE_CACHE = {}


def load_module(module_id, module_path):
    """Dynamically load a Python module"""
    if module_id in MODULE_CACHE:
        return MODULE_CACHE[module_id]

    try:
        # Convert relative path to absolute
        full_path = Path(__file__).parent.parent / module_path / "app.py"

        if not full_path.exists():
            print(f"⚠ Module {module_id} not found at {full_path}")
            return None

        # Load module
        spec = importlib.util.spec_from_file_location(f"module_{module_id}", full_path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"module_{module_id}"] = module
        spec.loader.exec_module(module)

        # Cache the Flask app
        if hasattr(module, 'app'):
            MODULE_CACHE[module_id] = module.app
            print(f"✓ Loaded module {module_id}")
            return module.app

        return None
    except Exception as e:
        print(f"✗ Error loading module {module_id}: {e}")
        return None


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "unified_backend",
        "modules_loaded": len(MODULE_CACHE),
        "total_modules": len(SERVICE_REGISTRY),
        "registry_loaded": len(SERVICE_REGISTRY) > 0
    })


@app.route('/api/services', methods=['GET'])
def list_services():
    """List all available services"""
    services = []
    for module_id, info in SERVICE_REGISTRY.items():
        services.append({
            "id": module_id,
            "name": info.get("name", "Unknown"),
            "type": info.get("type", "unknown"),
            "category": info.get("category", "unknown"),
            "path": info.get("path", ""),
            "endpoints": info.get("endpoints", [])
        })

    return jsonify({
        "total": len(services),
        "services": services
    })


@app.route('/api/<category>/<module_id>/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy_request(category, module_id, endpoint):
    """
    Proxy requests to specific modules
    Example: /api/backend/a-001/api/github/import
    """
    # Find module in registry
    if module_id not in SERVICE_REGISTRY:
        return jsonify({"error": f"Module {module_id} not found"}), 404

    module_info = SERVICE_REGISTRY[module_id]
    module_path = module_info.get("path")

    if not module_path:
        return jsonify({"error": f"No path for module {module_id}"}), 404

    # Load module
    module_app = load_module(module_id, module_path)

    if not module_app:
        return jsonify({"error": f"Failed to load module {module_id}"}), 500

    try:
        # Forward the request to the module
        with module_app.test_client() as client:
            # Reconstruct the endpoint path
            full_endpoint = f"/{endpoint}"

            # Forward request based on method
            if request.method == 'GET':
                response = client.get(full_endpoint, query_string=request.args)
            elif request.method == 'POST':
                response = client.post(
                    full_endpoint,
                    data=request.get_data(),
                    content_type=request.content_type,
                    headers=dict(request.headers)
                )
            elif request.method == 'PUT':
                response = client.put(
                    full_endpoint,
                    data=request.get_data(),
                    content_type=request.content_type,
                    headers=dict(request.headers)
                )
            elif request.method == 'DELETE':
                response = client.delete(full_endpoint)
            elif request.method == 'PATCH':
                response = client.patch(
                    full_endpoint,
                    data=request.get_data(),
                    content_type=request.content_type,
                    headers=dict(request.headers)
                )
            else:
                return jsonify({"error": "Method not allowed"}), 405

            # Return response
            return response.get_data(), response.status_code, dict(response.headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def index():
    """Serve the AI-generated dashboard UI"""
    dashboard_path = Path(__file__).parent / 'dashboard.html'

    if dashboard_path.exists():
        try:
            with open(dashboard_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading dashboard: {e}")
            return jsonify({
                "error": "Dashboard not found",
                "service": "Unified Backend Service",
                "version": "1.0.0",
                "endpoints": {
                    "health": "/health",
                    "services": "/api/services",
                    "module_api": "/api/<category>/<module_id>/<endpoint>"
                }
            })

    # Fallback if dashboard doesn't exist
    return jsonify({
        "service": "Unified Backend Service",
        "version": "1.0.0",
        "total_modules": len(SERVICE_REGISTRY),
        "modules_loaded": len(MODULE_CACHE),
        "endpoints": {
            "health": "/health",
            "services": "/api/services",
            "module_api": "/api/<category>/<module_id>/<endpoint>"
        },
        "note": "Dashboard HTML not found. Generate it using generate_ui_from_prompts.py"
    })


if __name__ == '__main__':
    print("=" * 80)
    print("UNIFIED BACKEND SERVICE STARTING")
    print("=" * 80)
    print(f"Modules in registry: {len(SERVICE_REGISTRY)}")
    print(f"Listening on: http://0.0.0.0:5000")
    print("=" * 80)
    app.run(host='0.0.0.0', port=5000, debug=False)