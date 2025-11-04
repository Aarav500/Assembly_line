import os
from flask import Flask, jsonify


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return jsonify({
            "message": "Hello from Flask!",
            "service": os.environ.get("SERVICE_NAME", "image-signing-cosign-demo")
        })

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.route("/version")
    def version():
        return jsonify({
            "version": os.environ.get("APP_VERSION", "dev"),
            "commit": os.environ.get("GIT_SHA", ""),
            "build_date": os.environ.get("BUILD_DATE", ""),
            "source": os.environ.get("VCS_URL", "")
        })

    return app


app = create_app()

