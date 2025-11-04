from flask import Blueprint, jsonify, current_app
from .utils import sanitize_config

bp = Blueprint("main", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/config")
def get_config():
    cfg = current_app.config.get("APP_CONFIG", {})
    return jsonify(sanitize_config(cfg))

