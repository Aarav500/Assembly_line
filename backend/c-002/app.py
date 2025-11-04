import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "Hello, World!"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/greet/<name>')
def greet(name):
    return jsonify({"greeting": f"Hello, {name}!"})

if __name__ == '__main__':
    app.run(debug=True)


def create_app():
    return app


@app.route('/api/greet/Alice', methods=['GET'])
def _auto_stub_api_greet_Alice():
    return 'Auto-generated stub for /api/greet/Alice', 200


@app.route('/todos', methods=['GET', 'POST'])
def _auto_stub_todos():
    return 'Auto-generated stub for /todos', 200


@app.route('/todos/999999', methods=['PUT'])
def _auto_stub_todos_999999():
    return 'Auto-generated stub for /todos/999999', 200
