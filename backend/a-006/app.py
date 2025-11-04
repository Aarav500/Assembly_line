import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
from flask import Flask, jsonify, render_template, request

from analyzer.scanner import scan_codebase


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    
    # Set a default secret key for testing if not provided
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['TESTING'] = os.environ.get('TESTING', 'False').lower() == 'true'

    @app.route("/")
    def index():
        try:
            return render_template("index.html")
        except Exception:
            # Return a simple HTML page if template is missing
            return '''<!DOCTYPE html>
<html>
<head><title>Codebase Analyzer</title></head>
<body>
<h1>Codebase Static Analysis Dashboard</h1>
<p>Use /api/scan?path=<path> to scan a codebase</p>
</body>
</html>'''

    @app.route("/api/scan")
    def api_scan():
        base_path = request.args.get("path") or os.environ.get("CODEBASE_PATH") or "."
        base_path = os.path.abspath(base_path)
        try:
            result = scan_codebase(base_path)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e), "base_path": base_path}), 500

    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "timestamp": time.time()}

    @app.route('/ready')
    def readiness_check():
        """Readiness check endpoint"""
        return {"status": "ready"}

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")