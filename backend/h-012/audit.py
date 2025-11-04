from flask import Blueprint, request, jsonify, g
from models import AuditLog, RoleEnum
from utils import jwt_required, roles_required

bp = Blueprint("audit", __name__, url_prefix="/audit")

@bp.route("/logs", methods=["GET"])
@jwt_required
@roles_required(RoleEnum.admin)
def list_logs():
    q = AuditLog.query
    user_id = request.args.get("user_id")
    action = request.args.get("action")
    success = request.args.get("success")
    limit = int(request.args.get("limit", 100))
    if user_id:
        q = q.filter(AuditLog.user_id == int(user_id))
    if action:
        q = q.filter(AuditLog.action == action)
    if success is not None:
        if success.lower() in ("true", "1"):
            q = q.filter(AuditLog.success.is_(True))
        elif success.lower() in ("false", "0"):
            q = q.filter(AuditLog.success.is_(False))
    q = q.order_by(AuditLog.id.desc()).limit(min(limit, 1000))
    records = [l.to_dict() for l in q.all()]
    return jsonify({"logs": records})

@bp.route("/logs/<int:log_id>", methods=["GET"])
@jwt_required
@roles_required(RoleEnum.admin)
def get_log(log_id):
    log = AuditLog.query.get(log_id)
    if not log:
        return jsonify({"error": "Log not found"}), 404
    return jsonify({"log": log.to_dict()})

