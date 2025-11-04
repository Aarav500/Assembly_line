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

@app.route('/api/data')
def get_data():
    return jsonify({"data": [1, 2, 3, 4, 5]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


def create_app():
    return app
