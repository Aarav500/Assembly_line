from flask import Flask, jsonify
import os


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return jsonify({"status": "ok", "message": "SBOM and license CI demo"})

    @app.route("/healthz")
    def health():
        return "ok", 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

