from flask import Blueprint, jsonify
import os

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify(status="ok", version=os.getenv("APP_VERSION", "1.0.0")), 200


@bp.get("/ready")
def ready():
    return jsonify(status="ready"), 200

