import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "Hello, World!", "status": "running"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/info')
def info():
    return jsonify({"app": "Flask API", "version": "1.0.0"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)



def create_app():
    return app
