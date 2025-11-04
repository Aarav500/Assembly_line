from flask import Blueprint, jsonify, make_response

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return make_response(
        jsonify({
            "status": "ok",
            "service": "todo-api",
            "version": "1.0.0"
        }),
        200,
    )
