import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# In-memory feature flags store
feature_flags = {
    "new_ui": False,
    "beta_feature": False,
    "advanced_search": True
}

@app.route('/')
def index():
    return jsonify({"message": "Feature Flag Service", "status": "running"})

@app.route('/flags', methods=['GET'])
def get_flags():
    return jsonify(feature_flags)

@app.route('/flags/<flag_name>', methods=['GET'])
def get_flag(flag_name):
    if flag_name in feature_flags:
        return jsonify({"flag": flag_name, "enabled": feature_flags[flag_name]})
    return jsonify({"error": "Flag not found"}), 404

@app.route('/flags/<flag_name>', methods=['PUT'])
def update_flag(flag_name):
    data = request.get_json()
    if flag_name not in feature_flags:
        return jsonify({"error": "Flag not found"}), 404
    
    if 'enabled' not in data:
        return jsonify({"error": "Missing 'enabled' field"}), 400
    
    feature_flags[flag_name] = bool(data['enabled'])
    return jsonify({"flag": flag_name, "enabled": feature_flags[flag_name]})

@app.route('/feature/<feature_name>', methods=['GET'])
def check_feature(feature_name):
    enabled = feature_flags.get(feature_name, False)
    return jsonify({
        "feature": feature_name,
        "enabled": enabled,
        "message": f"Feature '{feature_name}' is {'enabled' if enabled else 'disabled'}"
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app


@app.route('/flags/new_ui', methods=['GET', 'PUT'])
def _auto_stub_flags_new_ui():
    return 'Auto-generated stub for /flags/new_ui', 200


@app.route('/feature/advanced_search', methods=['GET'])
def _auto_stub_feature_advanced_search():
    return 'Auto-generated stub for /feature/advanced_search', 200
