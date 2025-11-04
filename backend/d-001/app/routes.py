from flask import Blueprint, jsonify

bp = Blueprint("routes", __name__)


@bp.get("/")
def index():
    return jsonify(status="ok", message="Hello, world!")

