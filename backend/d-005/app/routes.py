from flask import Blueprint, jsonify
import os

bp = Blueprint("routes", __name__)

@bp.route("/healthz")
def healthz():
    return jsonify(status="ok")

@bp.route("/")
def index():
    return jsonify(
        message="Hello from Flask with multi-stage Docker build and cache optimization!",
        env=os.environ.get("APP_ENV", "unknown"),
    )

