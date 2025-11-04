from typing import Any, Callable, Dict, List

from .base import bool_flag, int_value, str_value, mark_pass, mark_fail, mark_skip


CATEGORY = "gdpr"


def _gdpr_applicable(cfg: Dict[str, Any]) -> bool:
    # GDPR applies if you have EU users or operate in EU.
    eu_users = bool_flag(cfg, "general.eu_users", True)  # default True to encourage compliance
    return eu_users


def check_lawful_basis(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.lawful_basis"
    title = "Lawful basis for processing is documented"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "GDPR not applicable (no EU users)")
    v = bool_flag(cfg, "gdpr.lawful_basis_documented", False)
    if v:
        return mark_pass(id, title, CATEGORY, "high", "Lawful basis documented for relevant processing activities.", ["Art. 6 GDPR"])
    return mark_fail(
        id,
        title,
        CATEGORY,
        "high",
        "Missing documentation for lawful basis of processing.",
        "Document lawful basis (e.g., consent, contract, legitimate interests) for each processing activity.",
        ["Art. 6 GDPR", "Recital 40"]
    )


def check_dpo_assigned(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.dpo"
    title = "Data Protection Officer (DPO) assigned when required"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "GDPR not applicable (no EU users)")
    org_size = int_value(cfg, "general.org_size", 0)
    processes_special = bool_flag(cfg, "general.processes_special_categories", False)
    large_scale = org_size >= 250 or processes_special
    has_dpo = bool_flag(cfg, "gdpr.dpo_assigned", False)
    if large_scale and not has_dpo:
        return mark_fail(
            id,
            title,
            CATEGORY,
            "medium",
            "DPO is required (large scale or special categories) but none assigned.",
            "Appoint a qualified DPO and publish their contact details.",
            ["Art. 37-39 GDPR"]
        )
    return mark_pass(id, title, CATEGORY, "low", "DPO requirement met based on org profile.")


def check_data_minimization(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.data_minimization"
    title = "Data minimization policy exists and is enforced"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "GDPR not applicable (no EU users)")
    ok = bool_flag(cfg, "gdpr.data_minimization_policy", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "medium", "Data minimization policy is documented.", ["Art. 5(1)(c) GDPR"])
    return mark_fail(
        id,
        title,
        CATEGORY,
        "medium",
        "No data minimization policy found.",
        "Define and enforce a data minimization policy limiting collection to what is necessary.",
        ["Art. 5(1)(c) GDPR"]
    )


def check_dsar_process(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.dsar"
    title = "Data subject rights (DSAR) process documented"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "GDPR not applicable (no EU users)")
    ok = bool_flag(cfg, "gdpr.dsar_process_documented", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "high", "DSAR process documented and tested.", ["Art. 12-22 GDPR"])
    return mark_fail(
        id,
        title,
        CATEGORY,
        "high",
        "No DSAR handling process is documented.",
        "Establish procedures to authenticate, process, and log DSARs within statutory timelines.",
        ["Art. 12-22 GDPR"]
    )


def check_breach_notification(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.breach_notification"
    title = "Breach notification procedure exists"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "GDPR not applicable (no EU users)")
    ok = bool_flag(cfg, "gdpr.breach_notification_procedure", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "high", "Breach notification plan documented.", ["Art. 33-34 GDPR"])
    return mark_fail(
        id,
        title,
        CATEGORY,
        "high",
        "Missing data breach notification procedure.",
        "Define a breach response runbook, including assessment and notification within 72 hours where required.",
        ["Art. 33-34 GDPR"]
    )


def check_ropa(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.ropa"
    title = "Records of Processing Activities (ROPA) maintained"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "GDPR not applicable (no EU users)")
    ok = bool_flag(cfg, "gdpr.ropa_maintained", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "medium", "ROPA is maintained.", ["Art. 30 GDPR"])
    return mark_fail(id, title, CATEGORY, "medium", "No ROPA maintained.", "Create and maintain ROPA for processing activities.", ["Art. 30 GDPR"])


def check_retention_policy(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.retention"
    title = "Data retention policy exists"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "GDPR not applicable (no EU users)")
    ok = bool_flag(cfg, "gdpr.data_retention_policy", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "medium", "Data retention policy defined.", ["Art. 5(1)(e) GDPR"])
    return mark_fail(id, title, CATEGORY, "medium", "Missing data retention policy.", "Define and enforce retention and deletion schedules.", ["Art. 5(1)(e) GDPR"])


def check_cross_border(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.cross_border"
    title = "Cross-border transfer mechanism in place when needed"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "high", "GDPR not applicable (no EU users)")
    mech = str_value(cfg, "gdpr.cross_border_transfer_mechanism", "").strip().upper()
    using_non_eu = bool_flag(cfg, "general.uses_non_eu_processors", False)
    if not using_non_eu:
        return mark_skip(id, title, CATEGORY, "medium", "No non-EU data transfers in scope")
    if mech in {"SCC", "BCR", "ADEQUACY"}:
        return mark_pass(id, title, CATEGORY, "high", f"Transfer mechanism in place: {mech}.", ["Art. 46 GDPR"])
    return mark_fail(id, title, CATEGORY, "high", "No valid transfer mechanism for non-EU processing.", "Adopt SCCs/BCRs or ensure adequacy for cross-border transfers.", ["Art. 46 GDPR"])


def check_cookie_consent(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.cookie_consent"
    title = "Cookie consent management for web app"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "medium", "GDPR not applicable (no EU users)")
    is_web = bool_flag(cfg, "general.web_app", False)
    if not is_web:
        return mark_skip(id, title, CATEGORY, "low", "No web app in scope")
    ok = bool_flag(cfg, "gdpr.cookie_consent_management", False)
    if ok:
        return mark_pass(id, title, CATEGORY, "medium", "Cookie consent and preferences management in place.", ["ePrivacy", "Art. 7 GDPR"])
    return mark_fail(id, title, CATEGORY, "medium", "Cookie consent not implemented.", "Implement a consent CMP with granular controls and audit logs.")


def check_privacy_policy(cfg: Dict[str, Any]) -> Dict[str, Any]:
    id = "gdpr.privacy_policy"
    title = "Privacy policy published and accessible"
    if not _gdpr_applicable(cfg):
        return mark_skip(id, title, CATEGORY, "low", "GDPR not applicable (no EU users)")
    url = str_value(cfg, "gdpr.privacy_policy_url", "").strip() or str_value(cfg, "gdpr.privacy_policy", "").strip()
    if url:
        return mark_pass(id, title, CATEGORY, "medium", f"Privacy policy available at {url}.", ["Art. 12-14 GDPR"])
    return mark_fail(id, title, CATEGORY, "medium", "No accessible privacy policy URL.", "Publish and link a transparent privacy policy covering key disclosures.", ["Art. 12-14 GDPR"])


def gdpr_checks() -> List[Callable[[Dict[str, Any]], Dict[str, Any]]]:
    return [
        check_lawful_basis,
        check_dpo_assigned,
        check_data_minimization,
        check_dsar_process,
        check_breach_notification,
        check_ropa,
        check_retention_policy,
        check_cross_border,
        check_cookie_consent,
        check_privacy_policy,
    ]

