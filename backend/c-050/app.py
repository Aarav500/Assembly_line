import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import json
import os

app = Flask(__name__)

DATA_DIR = 'data'
EXPORT_FILE = os.path.join(DATA_DIR, 'export.json')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

sample_data = {
    'users': [
        {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'},
        {'id': 2, 'name': 'Bob', 'email': 'bob@example.com'},
        {'id': 3, 'name': 'Charlie', 'email': 'charlie@example.com'}
    ],
    'products': [
        {'id': 1, 'name': 'Laptop', 'price': 999.99},
        {'id': 2, 'name': 'Mouse', 'price': 29.99},
        {'id': 3, 'name': 'Keyboard', 'price': 79.99}
    ]
}

@app.route('/')
def home():
    return jsonify({'message': 'Dataset Export/Import Demo API', 'endpoints': ['/export', '/import', '/data']})

@app.route('/export', methods=['GET'])
def export_data():
    with open(EXPORT_FILE, 'w') as f:
        json.dump(sample_data, f, indent=2)
    return jsonify({'message': 'Data exported successfully', 'file': EXPORT_FILE})

@app.route('/import', methods=['POST'])
def import_data():
    if os.path.exists(EXPORT_FILE):
        with open(EXPORT_FILE, 'r') as f:
            imported_data = json.load(f)
        return jsonify({'message': 'Data imported successfully', 'data': imported_data})
    return jsonify({'error': 'No export file found'}), 404

@app.route('/data', methods=['GET'])
def get_data():
    return jsonify(sample_data)

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app
