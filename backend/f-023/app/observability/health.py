from flask import Blueprint, jsonify

health_blueprint = Blueprint("health", __name__)


@health_blueprint.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@health_blueprint.route("/readyz")
def readyz():
    # In production, add checks for dependencies, config, etc.
    return jsonify({"status": "ready"})

