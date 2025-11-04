import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({"message": "Hello, World!"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/echo", methods=["POST"])
def echo():
    data = request.get_json()
    return jsonify({"echo": data}), 200


if __name__ == "__main__":
    app.run(debug=True)



def create_app():
    return app


@app.route('/api/health', methods=['GET'])
def _auto_stub_api_health():
    return 'Auto-generated stub for /api/health', 200
