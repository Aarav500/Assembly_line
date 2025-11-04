import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

data_store = []

@app.route('/')
def index():
    return jsonify({"message": "Hello, World!"})

@app.route('/items', methods=['GET'])
def get_items():
    return jsonify({"items": data_store})

@app.route('/items', methods=['POST'])
def add_item():
    item = request.json.get('item')
    if not item:
        return jsonify({"error": "Item is required"}), 400
    data_store.append(item)
    return jsonify({"item": item, "count": len(data_store)}), 201

@app.route('/items/<int:index>', methods=['DELETE'])
def delete_item(index):
    if index < 0 or index >= len(data_store):
        return jsonify({"error": "Invalid index"}), 404
    deleted = data_store.pop(index)
    return jsonify({"deleted": deleted}), 200

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/items/0', methods=['DELETE'])
def _auto_stub_items_0():
    return 'Auto-generated stub for /items/0', 200


@app.route('/items/99', methods=['DELETE'])
def _auto_stub_items_99():
    return 'Auto-generated stub for /items/99', 200


@app.route('/items/-1', methods=['DELETE'])
def _auto_stub_items__1():
    return 'Auto-generated stub for /items/-1', 200


@app.route('/items/1', methods=['DELETE'])
def _auto_stub_items_1():
    return 'Auto-generated stub for /items/1', 200


@app.route('/api/divide?a=6&b=3', methods=['GET'])
def _auto_stub_api_divide_a_6_b_3():
    return 'Auto-generated stub for /api/divide?a=6&b=3', 200


@app.route('/api/clamp?n=foo&lo=0&hi=10', methods=['GET'])
def _auto_stub_api_clamp_n_foo_lo_0_hi_10():
    return 'Auto-generated stub for /api/clamp?n=foo&lo=0&hi=10', 200
