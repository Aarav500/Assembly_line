import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from functools import wraps
import time

app = Flask(__name__)

# In-memory storage
tenants = {
    "tenant1": {
        "models": ["gpt-4", "gpt-3.5"],
        "quota": {"gpt-4": 100, "gpt-3.5": 1000},
        "usage": {"gpt-4": 0, "gpt-3.5": 0}
    },
    "tenant2": {
        "models": ["gpt-3.5"],
        "quota": {"gpt-3.5": 500},
        "usage": {"gpt-3.5": 0}
    }
}

users = {
    "user1": {"tenant": "tenant1", "api_key": "key1"},
    "user2": {"tenant": "tenant2", "api_key": "key2"}
}

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"error": "Missing API key"}), 401
        
        user = None
        for username, data in users.items():
            if data["api_key"] == api_key:
                user = username
                break
        
        if not user:
            return jsonify({"error": "Invalid API key"}), 401
        
        request.user = user
        request.tenant = users[user]["tenant"]
        return f(*args, **kwargs)
    return decorated_function

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/models', methods=['GET'])
@require_auth
def get_models():
    tenant = request.tenant
    tenant_data = tenants.get(tenant, {})
    return jsonify({
        "tenant": tenant,
        "models": tenant_data.get("models", []),
        "quota": tenant_data.get("quota", {}),
        "usage": tenant_data.get("usage", {})
    }), 200

@app.route('/call', methods=['POST'])
@require_auth
def call_model():
    tenant = request.tenant
    data = request.get_json()
    
    if not data or 'model' not in data:
        return jsonify({"error": "Model name required"}), 400
    
    model = data['model']
    tenant_data = tenants.get(tenant)
    
    if not tenant_data:
        return jsonify({"error": "Tenant not found"}), 404
    
    # Check if model is allowed
    if model not in tenant_data["models"]:
        return jsonify({"error": f"Model {model} not accessible for tenant {tenant}"}), 403
    
    # Check quota
    if tenant_data["usage"].get(model, 0) >= tenant_data["quota"].get(model, 0):
        return jsonify({"error": f"Quota exceeded for model {model}"}), 429
    
    # Increment usage
    tenant_data["usage"][model] = tenant_data["usage"].get(model, 0) + 1
    
    return jsonify({
        "success": True,
        "model": model,
        "tenant": tenant,
        "remaining_quota": tenant_data["quota"][model] - tenant_data["usage"][model]
    }), 200

@app.route('/admin/tenant', methods=['POST'])
def create_tenant():
    data = request.get_json()
    tenant_id = data.get('tenant_id')
    models = data.get('models', [])
    quota = data.get('quota', {})
    
    if not tenant_id:
        return jsonify({"error": "tenant_id required"}), 400
    
    tenants[tenant_id] = {
        "models": models,
        "quota": quota,
        "usage": {model: 0 for model in models}
    }
    
    return jsonify({"tenant_id": tenant_id, "created": True}), 201

if __name__ == '__main__':
    app.run(debug=True, port=5000)



def create_app():
    return app
