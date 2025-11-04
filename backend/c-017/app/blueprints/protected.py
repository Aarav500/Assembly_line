from flask import Blueprint, jsonify
from ..rbac.decorators import roles_required, permissions_required

protected_bp = Blueprint("protected", __name__)


@protected_bp.route("/public")
def public():
    return jsonify({"message": "Public endpoint (no auth)"})


@protected_bp.route("/admin/secret")
@roles_required("admin")
def admin_secret():
    return jsonify({"message": "Top secret for admins"})


@protected_bp.route("/perms/secret")
@permissions_required("view:secret")
def perms_secret():
    return jsonify({"message": "Top secret for users with view:secret"})

