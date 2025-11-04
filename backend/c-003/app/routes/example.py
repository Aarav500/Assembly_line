from flask import Blueprint, jsonify, request

bp = Blueprint("api", __name__)


@bp.get("/hello")
def hello():
    name = request.args.get("name", "world")
    return jsonify(message=f"Hello, {name}!"), 200


@bp.post("/echo")
def echo():
    data = request.get_json(silent=True) or {}
    return jsonify(received=True, data=data), 200

