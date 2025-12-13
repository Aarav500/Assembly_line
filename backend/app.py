"""
UNIFIED BACKEND SERVICE
Dynamically loads and routes to all 437 modules in a SINGLE service

Save as: D:/Assemblyline/unified_app/unified_backend/app.py
"""

import os
import sys
import json
import importlib.util
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import NotFound

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

app = Flask(__name__)
CORS(app)

# Load service registry
REGISTRY_PATH = PROJECT_ROOT / "service_registry.json"
with open(REGISTRY_PATH) as f:
    SERVICE_REGISTRY = json.load(f)

# Cache for loaded modules
MODULE_CACHE = {}


def load_module_app(category: str, module_name: str):
    """Dynamically load a module's Flask app"""

    cache_key = f"{category}/{module_name}"

    # Return from cache if exists
    if cache_key in MODULE_CACHE:
        return MODULE_CACHE[cache_key]

    # Find module in registry
    if category not in SERVICE_REGISTRY:
        return None

    if module_name not in SERVICE_REGISTRY[category]:
        return None

    module_info = SERVICE_REGISTRY[category][module_name]
    module_path = PROJECT_ROOT / module_info['path']
    app_file = module_path / "app.py"

    if not app_file.exists():
        return None

    try:
        # Load module dynamically
        spec = importlib.util.spec_from_file_location(
            f"{category}.{module_name}",
            app_file
        )
        module = importlib.util.module_from_spec(spec)

        # Add module directory to sys.path temporarily
        sys.path.insert(0, str(module_path))

        spec.loader.exec_module(module)

        # Get the Flask app
        if hasattr(module, 'create_app'):
            module_app = module.create_app()
        elif hasattr(module, 'app'):
            module_app = module.app
        else:
            return None

        # Cache it
        MODULE_CACHE[cache_key] = module_app

        return module_app

    except Exception as e:
        print(f"Error loading {cache_key}: {e}")
        return None


@app.route('/health')
def health():
    """Health check for the unified service"""
    return jsonify({
        "status": "healthy",
        "service": "unified_backend",
        "total_modules": sum(len(v) for v in SERVICE_REGISTRY.values()),
        "loaded_modules": len(MODULE_CACHE)
    })


@app.route('/api/services')
def list_services():
    """List all available services"""
    services = []
    for category, modules in SERVICE_REGISTRY.items():
        for module_name, info in modules.items():
            services.append({
                "category": category,
                "name": module_name,
                "endpoints": info.get("api_endpoints", []),
                "description": info.get("description", "")
            })

    return jsonify({
        "services": services,
        "total": len(services)
    })


@app.route('/api/<category>/<module>/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy_to_module(category, module, endpoint):
    """
    Route requests to specific module
    Example: /api/backend/a-001/api/github/import
    """

    # Load the module's Flask app
    module_app = load_module_app(category, module)

    if not module_app:
        return jsonify({
            "error": f"Module {category}/{module} not found or failed to load"
        }), 404

    # Create a test client for the module
    with module_app.test_client() as client:
        try:
            # Forward the request
            if request.method == 'GET':
                response = client.get(
                    f'/{endpoint}',
                    query_string=request.query_string,
                    headers=dict(request.headers)
                )
            elif request.method == 'POST':
                response = client.post(
                    f'/{endpoint}',
                    data=request.get_data(),
                    content_type=request.content_type,
                    headers=dict(request.headers)
                )
            elif request.method == 'PUT':
                response = client.put(
                    f'/{endpoint}',
                    data=request.get_data(),
                    content_type=request.content_type,
                    headers=dict(request.headers)
                )
            elif request.method == 'DELETE':
                response = client.delete(
                    f'/{endpoint}',
                    headers=dict(request.headers)
                )
            elif request.method == 'PATCH':
                response = client.patch(
                    f'/{endpoint}',
                    data=request.get_data(),
                    content_type=request.content_type,
                    headers=dict(request.headers)
                )

            # Return the response
            return (response.get_data(), response.status_code, dict(response.headers))

        except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route('/')
def index():
    """Landing page"""
    return jsonify({
        "service": "Unified Backend",
        "version": "1.0.0",
        "total_modules": sum(len(v) for v in SERVICE_REGISTRY.values()),
        "endpoints": {
            "services": "/api/services",
            "health": "/health",
            "module_proxy": "/api/{category}/{module}/{endpoint}"
        }
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)