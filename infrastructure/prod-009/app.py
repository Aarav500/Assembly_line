import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify
from dotenv import load_dotenv

from config import Config
from auth.routes import auth_bp
from auth.routes import protected_bp


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config())

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(protected_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

