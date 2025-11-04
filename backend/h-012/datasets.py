from flask import Blueprint, request, jsonify, g
from models import db, Dataset, DatasetAccess, RoleEnum, ClassificationEnum, User
from utils import jwt_required, roles_required, log_audit, user_can_read_dataset, require_dataset_read_access, is_owner_or_admin

bp = Blueprint("datasets", __name__, url_prefix="/datasets")

@bp.route("", methods=["GET"])
@jwt_required
def list_datasets():
    user = g.current_user
    datasets = Dataset.query.all()
    visible = []
    for ds in datasets:
        if user_can_read_dataset(user, ds):
            visible.append(ds.to_meta_dict())
    log_audit("dataset.list", resource_type="dataset", resource_id=None, success=True, message=f"Returned {len(visible)} datasets")
    return jsonify({"datasets": visible})

@bp.route("", methods=["POST"])
@jwt_required
def create_dataset():
    user: User = g.current_user
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = data.get("description")
    classification = data.get("classification", ClassificationEnum.public)
    payload = data.get("data")
    try:
        classification = ClassificationEnum(classification)
    except Exception:
        return jsonify({"error": "Invalid classification"}), 400
    if not name:
        return jsonify({"error": "name is required"}), 400
    if Dataset.query.filter_by(name=name).first():
        return jsonify({"error": "Dataset name already exists"}), 409
    # Allow admins to create any dataset; analysts can create up to confidential; viewers cannot create
    if user.role == RoleEnum.viewer:
        return jsonify({"error": "Forbidden: viewers cannot create datasets"}), 403
    if user.role == RoleEnum.analyst and classification == ClassificationEnum.restricted:
        return jsonify({"error": "Analysts cannot create restricted datasets"}), 403
    ds = Dataset(name=name, description=description, classification=classification, data=payload, owner_id=user.id)
    db.session.add(ds)
    db.session.commit()
    log_audit("dataset.create", resource_type="dataset", resource_id=ds.id, success=True, message=f"Created dataset {name} ({classification.value})")
    return jsonify({"dataset": ds.to_meta_dict()}), 201

@bp.route("/<int:dataset_id>", methods=["GET"])
@jwt_required
@require_dataset_read_access
def get_dataset(dataset_id):
    ds: Dataset = g.dataset
    response = ds.to_meta_dict()
    # Only include data if user has read permission beyond public implicit visibility
    include_data = user_can_read_dataset(g.current_user, ds)
    if include_data:
        response["data"] = ds.data
    log_audit("dataset.read", resource_type="dataset", resource_id=ds.id, success=True, message="Dataset metadata returned with{} data".format("" if include_data else "out"))
    return jsonify({"dataset": response})

@bp.route("/<int:dataset_id>/grant", methods=["POST"])
@jwt_required
def grant_access(dataset_id):
    user = g.current_user
    ds = db.session.get(Dataset, dataset_id)
    if not ds:
        log_audit("dataset.grant", resource_type="dataset", resource_id=dataset_id, success=False, message="Dataset not found")
        return jsonify({"error": "Dataset not found"}), 404
    if not is_owner_or_admin(user, ds):
        log_audit("dataset.grant", resource_type="dataset", resource_id=dataset_id, success=False, message="Not owner/admin")
        return jsonify({"error": "Only owner or admin can grant access"}), 403
    body = request.get_json(silent=True) or {}
    target_user_id = body.get("user_id")
    can_read = bool(body.get("can_read", True))
    if not target_user_id:
        return jsonify({"error": "user_id required"}), 400
    target = db.session.get(User, int(target_user_id))
    if not target:
        return jsonify({"error": "Target user not found"}), 404
    existing = DatasetAccess.query.filter_by(user_id=target.id, dataset_id=ds.id).first()
    if existing:
        existing.can_read = can_read
        existing.granted_by = user.id
        db.session.commit()
        log_audit("dataset.grant", resource_type="dataset", resource_id=ds.id, success=True, message=f"Updated access for user {target.id}")
        return jsonify({"access": {"user_id": target.id, "dataset_id": ds.id, "can_read": existing.can_read}})
    access = DatasetAccess(user_id=target.id, dataset_id=ds.id, can_read=can_read, granted_by=user.id)
    db.session.add(access)
    db.session.commit()
    log_audit("dataset.grant", resource_type="dataset", resource_id=ds.id, success=True, message=f"Granted access to user {target.id}")
    return jsonify({"access": {"user_id": target.id, "dataset_id": ds.id, "can_read": can_read}}), 201

@bp.route("/<int:dataset_id>/revoke", methods=["POST"])
@jwt_required
def revoke_access(dataset_id):
    user = g.current_user
    ds = db.session.get(Dataset, dataset_id)
    if not ds:
        log_audit("dataset.revoke", resource_type="dataset", resource_id=dataset_id, success=False, message="Dataset not found")
        return jsonify({"error": "Dataset not found"}), 404
    if not is_owner_or_admin(user, ds):
        log_audit("dataset.revoke", resource_type="dataset", resource_id=dataset_id, success=False, message="Not owner/admin")
        return jsonify({"error": "Only owner or admin can revoke access"}), 403
    body = request.get_json(silent=True) or {}
    target_user_id = body.get("user_id")
    if not target_user_id:
        return jsonify({"error": "user_id required"}), 400
    access = DatasetAccess.query.filter_by(user_id=int(target_user_id), dataset_id=ds.id).first()
    if not access:
        return jsonify({"error": "Access not found"}), 404
    db.session.delete(access)
    db.session.commit()
    log_audit("dataset.revoke", resource_type="dataset", resource_id=ds.id, success=True, message=f"Revoked access for user {target_user_id}")
    return jsonify({"status": "revoked", "user_id": int(target_user_id), "dataset_id": ds.id})

@bp.route("/<int:dataset_id>/acl", methods=["GET"])
@jwt_required
def list_acl(dataset_id):
    user = g.current_user
    ds = db.session.get(Dataset, dataset_id)
    if not ds:
        return jsonify({"error": "Dataset not found"}), 404
    if not is_owner_or_admin(user, ds):
        return jsonify({"error": "Only owner or admin can view ACL"}), 403
    accesses = DatasetAccess.query.filter_by(dataset_id=ds.id).all()
    acl = [{"user_id": a.user_id, "can_read": a.can_read, "granted_by": a.granted_by, "granted_at": a.granted_at.isoformat() + "Z"} for a in accesses]
    log_audit("dataset.acl_list", resource_type="dataset", resource_id=ds.id, success=True, message=f"Returned {len(acl)} ACL entries")
    return jsonify({"dataset_id": ds.id, "acl": acl})

