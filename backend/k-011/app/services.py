from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

from .models import Change, Proposal, ProposalStatus
from .storage import AppRepositories


def compute_diff(current: Optional[Dict[str, Any]], desired: Dict[str, Any]) -> List[Change]:
    changes: List[Change] = []
    current = current or {}

    # Only process keys present in desired. To remove, set value to None explicitly
    for key, desired_value in desired.items():
        if key not in current:
            op = "add"
            changes.append(Change(field=key, from_value=None, to_value=desired_value, op=op))
        else:
            current_value = current.get(key)
            if desired_value != current_value:
                op = "remove" if desired_value is None else "update"
                changes.append(Change(field=key, from_value=current_value, to_value=desired_value, op=op))
    return changes


def apply_changes_to_item(current: Optional[Dict[str, Any]], changes: List[Change]) -> Dict[str, Any]:
    result = dict(current or {})
    for ch in changes:
        if ch.op == "remove":
            result[ch.field] = None
        else:
            result[ch.field] = ch.to_value
    return result


def create_proposal(repos: AppRepositories, resource: str, target_id: str, desired: Dict[str, Any], agent_id: Optional[str]) -> Proposal:
    if resource != "items":
        raise ValueError("Unsupported resource: only 'items' is supported in this demo")

    current = repos.items.get_item(target_id)
    changes = compute_diff(current, desired)
    proposal = Proposal.new(resource=resource, target_id=target_id, changes=changes, agent_id=agent_id, original_snapshot=repos.items.snapshot_item(target_id))
    repos.proposals.add(proposal)
    return proposal


def apply_proposal(repos: AppRepositories, proposal: Proposal) -> Dict:
    if proposal.resource != "items":
        raise ValueError("Unsupported resource: only 'items' is supported in this demo")

    current = repos.items.get_item(proposal.target_id)
    updated = apply_changes_to_item(current, proposal.changes)
    repos.items.upsert_item(proposal.target_id, updated)

    # Mark as applied
    updated_proposal = repos.proposals.update(
        proposal.id,
        status=ProposalStatus.APPLIED.value,
    )
    return updated


def proposal_from_dict(data: Dict[str, Any]) -> Proposal:
    return Proposal(
        id=data["id"],
        resource=data["resource"],
        target_id=data["target_id"],
        status=ProposalStatus(data["status"]),
        changes=[Change(field=c["field"], from_value=c.get("from"), to_value=c.get("to"), op=c.get("op", "update")) for c in data.get("changes", [])],
        agent_id=data.get("agent_id"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        original_snapshot=data.get("original_snapshot"),
    )

