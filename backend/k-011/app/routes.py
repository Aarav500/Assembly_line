from flask import Blueprint, current_app, request
from typing import Any, Dict

from .storage import AppRepositories
from .services import create_proposal, apply_proposal, proposal_from_dict
from .models import ProposalStatus

api_bp = Blueprint("api", __name__)


def repos() -> AppRepositories:
    return AppRepositories(current_app.config["DATA_DIR"])  # fresh handles to file stores


@api_bp.get("/health")
def health():
    return {"status": "ok"}


@api_bp.get("/config")
def get_config():
    return {
        "sandbox_dry_run": bool(current_app.config["SANDBOX_DRY_RUN"]),
        "data_dir": current_app.config["DATA_DIR"],
    }


@api_bp.get("/items")
def list_items():
    r = repos()
    return {"items": r.items.list_items()}


@api_bp.get("/items/<item_id>")
def get_item(item_id: str):
    r = repos()
    item = r.items.get_item(item_id)
    if item is None:
        return {"error": "not_found", "message": f"item {item_id} not found"}, 404
    return {"id": item_id, "data": item}


@api_bp.post("/agents/changes")
def agent_changes():
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    agent_id = payload.get("agent_id")
    resource = payload.get("resource")
    target_id = payload.get("id")
    desired = payload.get("desired")
    auto_apply = bool(payload.get("auto_apply", False))

    if not resource or not target_id or not isinstance(desired, dict):
        return {"error": "invalid_request", "message": "Fields 'resource', 'id', and object 'desired' are required"}, 400

    r = repos()

    try:
        proposal = create_proposal(r, resource, target_id, desired, agent_id)
    except ValueError as ve:
        return {"error": "unsupported_resource", "message": str(ve)}, 400

    # No-op change when no differences
    if len(proposal.changes) == 0:
        return {
            "dry_run": bool(current_app.config["SANDBOX_DRY_RUN"]),
            "no_changes": True,
            "proposal": proposal.to_dict(),
            "applied": False,
        }, 200

    sandbox = bool(current_app.config["SANDBOX_DRY_RUN"])
    if sandbox:
        # Only produce proposal, no applying allowed
        return {
            "dry_run": True,
            "proposal": proposal.to_dict(),
            "applied": False,
            "message": "Sandbox dry-run mode: changes proposed only, not applied",
        }, 201

    # Not sandbox: either auto-apply or wait for approval
    if auto_apply:
        updated = apply_proposal(r, proposal)
        return {
            "dry_run": False,
            "proposal": r.proposals.get(proposal.id),
            "applied": True,
            "updated_item": {"id": proposal.target_id, "data": updated},
        }, 201

    return {
        "dry_run": False,
        "proposal": proposal.to_dict(),
        "applied": False,
        "message": "Proposal created; awaiting approval",
    }, 201


@api_bp.get("/proposals")
def list_proposals():
    r = repos()
    return {"proposals": r.proposals.list()}


@api_bp.get("/proposals/<proposal_id>")
def get_proposal(proposal_id: str):
    r = repos()
    p = r.proposals.get(proposal_id)
    if not p:
        return {"error": "not_found", "message": f"proposal {proposal_id} not found"}, 404
    return p


@api_bp.post("/proposals/<proposal_id>/approve")
def approve_proposal(proposal_id: str):
    if bool(current_app.config["SANDBOX_DRY_RUN"]):
        return {"error": "forbidden", "message": "Cannot approve in sandbox dry-run mode"}, 403

    r = repos()
    p = r.proposals.get(proposal_id)
    if not p:
        return {"error": "not_found", "message": f"proposal {proposal_id} not found"}, 404

    if p.get("status") in (ProposalStatus.REJECTED.value, ProposalStatus.APPLIED.value):
        return {"error": "invalid_state", "message": f"Cannot approve proposal in status {p.get('status')}"}, 400

    # Mark approved first, then apply
    r.proposals.update(proposal_id, status=ProposalStatus.APPROVED.value)
    proposal_obj = proposal_from_dict(r.proposals.get(proposal_id))

    updated_item = apply_proposal(r, proposal_obj)
    return {
        "proposal": r.proposals.get(proposal_id),
        "updated_item": {"id": proposal_obj.target_id, "data": updated_item},
    }


@api_bp.post("/proposals/<proposal_id>/reject")
def reject_proposal(proposal_id: str):
    r = repos()
    p = r.proposals.get(proposal_id)
    if not p:
        return {"error": "not_found", "message": f"proposal {proposal_id} not found"}, 404

    if p.get("status") in (ProposalStatus.APPLIED.value, ProposalStatus.REJECTED.value):
        return {"error": "invalid_state", "message": f"Cannot reject proposal in status {p.get('status')}"}, 400

    updated = r.proposals.update(proposal_id, status=ProposalStatus.REJECTED.value)
    return updated or ({"error": "server_error", "message": "Failed to update proposal"}, 500)

