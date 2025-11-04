from typing import Any, Callable, Dict, List

from .base import bool_flag, mark_pass, mark_fail, mark_skip


CATEGORY = "hipaa"


def _hipaa_applicable(cfg: Dict[str, Any]) -> bool:
    # Apply if handling PHI or acting as a covered entity/business associate
    return bool_flag(cfg, "general.processes_phi", False) or bool_flag(cfg, "hipaa.in_scope", True)


def check_risk_analysis(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.risk_analysis"
    title = "Risk analysis performed and documented"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "HIPAA not applicable")
    ok = bool_flag(cfg, "hipaa.risk_analysis_performed", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "high", "Risk analysis documented.", ["45 CFR 164.308(a)(1)(ii)(A)"])
    return mark_fail(id, title, CATEGORY, "high", "Missing documented risk analysis.", "Conduct a thorough risk analysis covering ePHI confidentiality, integrity, and availability.")


def check_training(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.training"
    title = "Workforce receives HIPAA security/privacy training"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "HIPAA not applicable")
    ok = bool_flag(cfg, "hipaa.workforce_training", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "medium", "Workforce training conducted.", ["45 CFR 164.308(a)(5)"])
    return mark_fail(id, title, CATEGORY, "medium", "No workforce HIPAA training program.", "Implement initial and periodic HIPAA training for all workforce members.")


def check_baa(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.baa"
    title = "Business Associate Agreements (BAAs) in place"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "HIPAA not applicable")
    ok = bool_flag(cfg, "hipaa.baas_in_place", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "high", "BAAs executed with relevant vendors.", ["45 CFR 164.308(b)"])
    return mark_fail(id, title, CATEGORY, "high", "BAAs missing for vendors handling PHI.", "Execute BAAs with all vendors that store or process PHI.")


def check_access_controls(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.access_controls"
    title = "Access controls: unique IDs, MFA, RBAC"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "HIPAA not applicable")
    unique = bool_flag(cfg, "hipaa.access_controls.unique_user_ids", False)
    mfa = bool_flag(cfg, "hipaa.access_controls.mfa_enabled", False)
    rbac = bool_flag(cfg, "hipaa.access_controls.role_based_access", False)
    if unique and mfa and rbac:
        return mark_pass(id, title, CATEGORY, "high", "Access controls implemented.", ["45 CFR 164.312(a)"])
    return mark_fail(id, title, CATEGORY, "high", "Access controls incomplete (need unique IDs, MFA, RBAC).", "Implement unique user IDs, enable MFA, and enforce RBAC with least privilege.")


def check_audit_controls(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.audit_controls"
    title = "Audit controls enabled for systems with ePHI"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "HIPAA not applicable")
    ok = bool_flag(cfg, "hipaa.audit_controls_enabled", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "high", "Audit logging enabled.", ["45 CFR 164.312(b)"])
    return mark_fail(id, title, CATEGORY, "high", "Audit controls not enabled for ePHI systems.", "Enable, monitor, and retain audit logs for systems handling ePHI.")


def check_encryption(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.encryption"
    title = "Encryption in transit and at rest for ePHI"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "HIPAA not applicable")
    at_rest = bool_flag(cfg, "hipaa.encryption.at_rest", False)
    in_transit = bool_flag(cfg, "hipaa.encryption.in_transit", False)
    if at_rest and in_transit:
        return mark_pass(id, title, CATEGORY, "high", "Encryption controls implemented.", ["45 CFR 164.312(a)(2)(iv)", "164.312(e)(2)(ii)"])
    return mark_fail(id, title, CATEGORY, "high", "Encryption controls incomplete (at rest and/or in transit missing).", "Encrypt ePHI at rest (e.g., AES-256) and in transit (TLS 1.2+).")


def check_incident_response(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.incident_response"
    title = "Incident response plan exists"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "HIPAA not applicable")
    ok = bool_flag(cfg, "hipaa.incident_response_plan", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "medium", "Incident response plan documented.", ["45 CFR 164.308(a)(6)"])
    return mark_fail(id, title, CATEGORY, "medium", "No incident response plan.", "Document and test an incident response plan including breach handling.")


def check_contingency_plan(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.contingency"
    title = "Contingency plan with backups and testing"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "HIPAA not applicable")
    backups = bool_flag(cfg, "hipaa.contingency_plan.backups", False)
    tested = bool_flag(cfg, "hipaa.contingency_plan.tested", False)
    if backups and tested:
        return mark_pass(id, title, CATEGORY, "medium", "Contingency plan implemented.", ["45 CFR 164.308(a)(7)"])
    return mark_fail(id, title, CATEGORY, "medium", "Contingency plan inadequate (backups and/or testing missing).", "Implement routine backups and periodic contingency plan testing.")


def check_minimum_necessary(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.minimum_necessary"
    title = "Minimum necessary standard enforced"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "HIPAA not applicable")
    ok = bool_flag(cfg, "hipaa.minimum_necessary_policy", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "medium", "Minimum necessary policy exists.", ["45 CFR 164.502(b)"])
    return mark_fail(id, title, CATEGORY, "medium", "No minimum necessary policy.", "Adopt and enforce a minimum necessary policy for PHI use and disclosure.")


def check_disposal_policy(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "hipaa.disposal"
    title = "Secure PHI disposal policy"
    if not _hipaa_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "low", "HIPAA not applicable")
    ok = bool_flag(cfg, "hipaa.phi_disposal_policy", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "low", "PHI disposal policy exists.", ["45 CFR 164.310(d)(2)(i)"])
    return mark_fail(id, title, CATEGORY, "medium", "No secure PHI disposal policy.", "Define procedures for secure PHI disposal (media sanitization, shredding, etc.).")


def hipaa_checks() -> List[Callable[[Dict[str, Any]], Dict[str, Any]]]:
    return [
        check_risk_analysis,
        check_training,
        check_baa,
        check_access_controls,
        check_audit_controls,
        check_encryption,
        check_incident_response,
        check_contingency_plan,
        check_minimum_necessary,
        check_disposal_policy,
    ]

