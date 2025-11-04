from typing import Optional
from database import db
from models import AuditLog, Stage, Gate, GateAllowedUser, GateApproval


def audit(actor_id: Optional[int], action: str, entity_type: str, entity_id: Optional[int], details: Optional[dict] = None):
    log = AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {})
    db.session.add(log)
    # do not commit here; caller commits transaction


def get_first_stage():
    return Stage.query.order_by(Stage.position.asc()).first()


def get_next_stage(current_stage_id: int):
    current_stage = Stage.query.get(current_stage_id)
    if not current_stage:
        return None
    return Stage.query.filter(Stage.position > current_stage.position).order_by(Stage.position.asc()).first()


def user_allowed_on_gate(user, gate: Gate) -> bool:
    # allowed by explicit user list
    if any(au.user_id == user.id for au in gate.allowed_users):
        return True
    # allowed by role
    roles = gate.allowed_role_list()
    if roles and user.role in roles:
        return True
    return False


def gate_approval_summary(deployment_id: int, gate_id: int):
    qs = GateApproval.query.filter_by(deployment_id=deployment_id, gate_id=gate_id)
    approvals = qs.filter_by(decision='approved').count()
    rejections = qs.filter_by(decision='rejected').count()
    return {'approved': approvals, 'rejected': rejections}


def stage_ready_for_advance(deployment, stage: Stage) -> (bool, dict):
    details = {}
    for gate in stage.gates:
        summary = gate_approval_summary(deployment.id, gate.id)
        details[str(gate.id)] = summary
        if summary['rejected'] > 0:
            return False, details
        if summary['approved'] < gate.required_approvals:
            return False, details
    return True, details

