from flask import Blueprint, jsonify, request
from utils.errors import APIError


def create_api_blueprint(manager):
    bp = Blueprint("api", __name__)

    @bp.get("/connectors")
    def list_connectors():
        return jsonify(manager.list_metadata())

    @bp.get("/<slug>/health")
    def connector_health(slug):
        conn = manager.get(slug)
        if not conn:
            raise APIError("Connector not found", 404)
        return jsonify(conn.safe_health())

    @bp.get("/<slug>/search")
    def connector_search(slug):
        conn = manager.get(slug)
        if not conn:
            raise APIError("Connector not found", 404)
        q = request.args.get("q", "").strip()
        if not q:
            raise APIError("Missing 'q' parameter", 400)
        if not conn.has_operation("search"):
            raise APIError("Search not supported for this connector", 400)
        res = conn.search(q)
        return jsonify(res)

    @bp.get("/<slug>/get")
    def connector_get(slug):
        conn = manager.get(slug)
        if not conn:
            raise APIError("Connector not found", 404)
        rid = request.args.get("id")
        if not rid:
            raise APIError("Missing 'id' parameter", 400)
        if not conn.has_operation("get"):
            raise APIError("Get not supported for this connector", 400)
        res = conn.get(rid)
        return jsonify(res)

    @bp.post("/<slug>/action")
    def connector_action(slug):
        conn = manager.get(slug)
        if not conn:
            raise APIError("Connector not found", 404)
        payload = request.get_json(silent=True) or {}
        action = payload.get("action")
        params = payload.get("params", {})
        if not action:
            raise APIError("Missing 'action' in request body", 400)
        if not conn.has_operation(action):
            raise APIError("Action not supported for this connector", 400)
        res = conn.perform_action(action, params)
        return jsonify(res)

    return bp

