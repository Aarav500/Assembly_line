from flask import Blueprint, jsonify, request, g, abort

from .db import db
from .models import Widget

api = Blueprint("api", __name__, url_prefix="/api")


@api.route("/whoami", methods=["GET"])
def whoami():
    if not getattr(g, "tenant_id", None):
        abort(400, description="Tenant not specified")
    return jsonify({
        "tenant_id": g.tenant_id,
        "tenant_schema": getattr(g, "tenant_schema", None),
    })


@api.route("/widgets", methods=["GET"])
def list_widgets():
    widgets = Widget.query.order_by(Widget.id.asc()).all()
    return jsonify([w.to_dict() for w in widgets])


@api.route("/widgets", methods=["POST"])
def create_widget():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, description="name is required")
    w = Widget(name=name)
    db.session.add(w)
    db.session.commit()
    return jsonify(w.to_dict()), 201

