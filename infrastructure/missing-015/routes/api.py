from flask import Blueprint, jsonify, request, g
from services.usage import get_usage

api_bp = Blueprint('api', __name__, url_prefix='/v1')


@api_bp.get('/ping')
def ping():
    return jsonify({"ok": True, "service": "quota-api"})


@api_bp.get('/usage')
def usage():
    user = getattr(g, 'user', None)
    tier = getattr(g, 'tier', None)
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    month_usage = get_usage(user['id'])
    resp = {
        "user": {
            "id": user["id"],
            "email": user.get("email"),
            "tier": user.get("tier"),
        },
        "usage": month_usage,
        "quota": int(tier.get("monthly_quota") or 0),
    }
    return jsonify(resp)


@api_bp.get('/data')
def get_data():
    # Sample protected resource
    return jsonify({"data": "Here is your protected data.", "user": g.user.get("id")})


@api_bp.post('/echo')
def echo():
    payload = request.get_json(silent=True) or {}
    return jsonify({"echo": payload, "user": g.user.get("id")})

