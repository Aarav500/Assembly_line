import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import os

app = Flask(__name__)

class PluginConnector:
    def __init__(self):
        self.plugins = {}
    
    def register_plugin(self, name, config):
        self.plugins[name] = config
        return True
    
    def get_plugin(self, name):
        return self.plugins.get(name)
    
    def list_plugins(self):
        return list(self.plugins.keys())
    
    def execute_plugin(self, name, action, params=None):
        if name not in self.plugins:
            return {"error": "Plugin not found"}
        return {
            "plugin": name,
            "action": action,
            "params": params,
            "status": "executed"
        }

connector = PluginConnector()

# Pre-register supported plugins
connector.register_plugin("notion", {"type": "document", "api_version": "v1"})
connector.register_plugin("figma", {"type": "design", "api_version": "v1"})
connector.register_plugin("jira", {"type": "project_management", "api_version": "v2"})
connector.register_plugin("slack", {"type": "communication", "api_version": "v1"})
connector.register_plugin("s3", {"type": "storage", "api_version": "v1"})
connector.register_plugin("database", {"type": "data", "api_version": "v1"})

@app.route("/")
def index():
    return jsonify({"message": "Global Plugin Connector System", "status": "running"})

@app.route("/plugins", methods=["GET"])
def list_plugins():
    plugins = connector.list_plugins()
    return jsonify({"plugins": plugins, "count": len(plugins)})

@app.route("/plugins/<name>", methods=["GET"])
def get_plugin(name):
    plugin = connector.get_plugin(name)
    if plugin:
        return jsonify({"name": name, "config": plugin})
    return jsonify({"error": "Plugin not found"}), 404

@app.route("/plugins/<name>/execute", methods=["POST"])
def execute_plugin(name):
    data = request.get_json() or {}
    action = data.get("action", "default")
    params = data.get("params", {})
    result = connector.execute_plugin(name, action, params)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)

@app.route("/plugins/register", methods=["POST"])
def register_plugin():
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "Plugin name required"}), 400
    name = data["name"]
    config = data.get("config", {})
    connector.register_plugin(name, config)
    return jsonify({"message": "Plugin registered", "name": name}), 201

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)


def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/api/connectors', methods=['GET'])
def _auto_stub_api_connectors():
    return 'Auto-generated stub for /api/connectors', 200
