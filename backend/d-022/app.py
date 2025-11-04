import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "Hello, World!", "status": "healthy"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/api/echo/<message>')
def echo(message):
    return jsonify({"echo": message})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app
