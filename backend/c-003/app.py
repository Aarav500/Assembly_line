import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "Welcome to Flask API", "framework": "Flask"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/echo', methods=['POST'])
def echo():
    data = request.get_json()
    return jsonify({"echoed": data})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app


@app.route('/api/v1/hello', methods=['GET'])
def _auto_stub_api_v1_hello():
    return 'Auto-generated stub for /api/v1/hello', 200


@app.route('/api/v1/hello?name=Alice', methods=['GET'])
def _auto_stub_api_v1_hello_name_Alice():
    return 'Auto-generated stub for /api/v1/hello?name=Alice', 200


@app.route('/api/v1/echo', methods=['POST'])
def _auto_stub_api_v1_echo():
    return 'Auto-generated stub for /api/v1/echo', 200


@app.route('/ready', methods=['GET'])
def _auto_stub_ready():
    return 'Auto-generated stub for /ready', 200
