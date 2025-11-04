from __future__ import annotations
from flask import Blueprint, jsonify, request
from .rbac import require_roles, sensitive

bp = Blueprint("routes", __name__)


# Automatic RBAC via path patterns: /admin/* requires admin
@bp.get("/admin/dashboard")
def admin_dashboard():
    return jsonify({"dashboard": "secret"})


# Automatic RBAC via path patterns: /billing/* requires admin or billing
@bp.post("/billing/charge")
def billing_charge():
    payload = request.get_json(silent=True) or {}
    amount = payload.get("amount")
    currency = payload.get("currency", "USD")
    if amount is None:
        return jsonify({"error": "bad_request", "reason": "amount required"}), 400
    return jsonify({"charged": float(amount), "currency": currency})


# Automatic RBAC via path patterns: /users/<id>/secrets requires admin or security
@bp.get("/users/<int:user_id>/secrets")
def user_secrets(user_id: int):
    return jsonify({"user_id": user_id, "secrets": ["token:last4:abcd", "flags:2"]})


# Automatic RBAC via path patterns: /tokens requires admin or security
@bp.post("/tokens/rotate")
def rotate_tokens():
    return jsonify({"rotated": True})


# Explicit decorator-based RBAC: allow support or admin
@bp.get("/support/cases")
@require_roles("support", "admin")
def list_support_cases():
    return jsonify({"cases": [{"id": 101, "status": "open"}, {"id": 102, "status": "pending"}]})


# Sensitive by semantic level: medium => security or admin (per config)
@bp.get("/audit/logs")
@sensitive("medium")
def audit_logs():
    return jsonify({"logs": [
        {"ts": "2025-01-01T00:00:00Z", "evt": "login", "user": "alice"},
        {"ts": "2025-01-01T01:00:00Z", "evt": "access", "user": "bob"}
    ]})

