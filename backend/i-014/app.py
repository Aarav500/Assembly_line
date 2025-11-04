import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, render_template
from security.manager import SecurityManager
import os


def create_app():
    app = Flask(__name__)

    # Basic Flask cookie/session security settings
    app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", os.urandom(32)))
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)  # Set True when serving over HTTPS

    # Initialize Security Manager with default policies
    security = SecurityManager()
    security.init_app(app)

    @app.get("/")
    def index():
        # Demonstrate inline script/style using CSP nonce helper
        return render_template("index.html")

    # Sample API endpoint
    @app.get("/api/data")
    def get_data():
        return jsonify({"message": "Hello, secure world!"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



@app.route('/api/suggestions', methods=['GET'])
def _auto_stub_api_suggestions():
    return 'Auto-generated stub for /api/suggestions', 200
