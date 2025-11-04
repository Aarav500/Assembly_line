import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from flask import Flask, request, jsonify, render_template
from werkzeug.exceptions import BadRequest
from validators import validate_inventory
from legal_rules import RuleEngine

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check', methods=['POST'])
def api_check():
    try:
        payload = request.get_json(force=True, silent=False)
    except BadRequest:
        return jsonify({"error": "Invalid JSON payload"}), 400

    ok, errors = validate_inventory(payload)
    if not ok:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    engine = RuleEngine()
    report = engine.run(payload)
    return jsonify(report)

@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(err):
    return jsonify({"error": "Server error", "details": str(err)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/data/collect', methods=['POST'])
def _auto_stub_data_collect():
    return 'Auto-generated stub for /data/collect', 200


@app.route('/data/user456', methods=['GET'])
def _auto_stub_data_user456():
    return 'Auto-generated stub for /data/user456', 200


@app.route('/data/user789', methods=['DELETE', 'GET'])
def _auto_stub_data_user789():
    return 'Auto-generated stub for /data/user789', 200


@app.route('/compliance/check', methods=['GET'])
def _auto_stub_compliance_check():
    return 'Auto-generated stub for /compliance/check', 200
