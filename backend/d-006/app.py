import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import subprocess
import os

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"message": "Image Signing Service", "status": "running"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/sign', methods=['POST'])
def sign_image():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"error": "image parameter required"}), 400
    
    image = data['image']
    key = data.get('key', os.getenv('COSIGN_KEY', 'cosign.key'))
    
    try:
        result = subprocess.run(
            ['cosign', 'sign', '--key', key, image],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return jsonify({
                "status": "success",
                "image": image,
                "output": result.stdout
            }), 200
        else:
            return jsonify({
                "status": "error",
                "error": result.stderr
            }), 500
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/verify', methods=['POST'])
def verify_image():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"error": "image parameter required"}), 400
    
    image = data['image']
    key = data.get('key', os.getenv('COSIGN_PUBLIC_KEY', 'cosign.pub'))
    
    try:
        result = subprocess.run(
            ['cosign', 'verify', '--key', key, image],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return jsonify({
                "status": "verified",
                "image": image,
                "output": result.stdout
            }), 200
        else:
            return jsonify({
                "status": "failed",
                "error": result.stderr
            }), 400
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app
