import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, request
from rate_limiter import FlaskRateLimiter, limit


def create_app():
    app = Flask(__name__)

    # Config via env vars (optional)
    app.config.setdefault("RATE_LIMIT_ENABLED", os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false")
    app.config.setdefault("RATE_LIMIT_DEFAULT", os.getenv("RATE_LIMIT_DEFAULT", "100/minute"))
    app.config.setdefault("RATE_LIMIT_HEADERS_ENABLED", os.getenv("RATE_LIMIT_HEADERS_ENABLED", "true").lower() == "true")
    app.config.setdefault("RATE_LIMIT_STORAGE_URL", os.getenv("RATE_LIMIT_STORAGE_URL", "memory://"))

    limiter = FlaskRateLimiter(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.route("/")
    def index():
        return jsonify(message="Welcome! This endpoint uses the default rate limit")

    # Per-route limit example
    @app.route("/search")
    @limit("30/minute")
    def search():
        q = request.args.get("q", "")
        return jsonify(results=[], query=q)

    # Shared group across multiple endpoints
    @app.route("/expensive-a")
    @limit("10/minute", scope="shared:expensive")
    def expensive_a():
        return jsonify(ok=True, route="A")

    @app.route("/expensive-b")
    @limit("10/minute", scope="shared:expensive")
    def expensive_b():
        return jsonify(ok=True, route="B")

    # Weighted cost example (POST counts more than GET)
    def dynamic_cost(req):
        return 5 if req.method == "POST" else 1

    @app.route("/ingest", methods=["GET", "POST"])
    @limit("100/hour", cost=dynamic_cost)
    def ingest():
        return jsonify(received=True, method=request.method)

    # Conditional exemption example (skip limit for internal IP)
    def exempt_internal():
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        return ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("127.")

    @app.route("/internal-only")
    @limit("5/minute", exempt_when=exempt_internal)
    def internal_only():
        return jsonify(access="granted")

    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app = create_app()
    app.run(host="0.0.0.0", port=port)



@app.route('/api/data', methods=['GET'])
def _auto_stub_api_data():
    return 'Auto-generated stub for /api/data', 200
