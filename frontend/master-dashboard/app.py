from flask import Flask, render_template, jsonify
import json
from pathlib import Path

app = Flask(__name__)

@app.route('/')
def dashboard():
    registry_path = Path(__file__).parent.parent.parent / "service_registry.json"
    with open(registry_path) as f:
        registry = json.load(f)
    return render_template('dashboard.html', registry=registry)

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
