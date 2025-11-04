from datetime import datetime, timezone


SAFETY_CRITICAL_DOMAINS = {"medical", "healthcare", "finance", "autonomous", "aviation", "biometric", "hiring", "law_enforcement", "education"}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v in ("true", "True", "1", 1):
        return True
    if v in ("false", "False", "0", 0):
        return False
    return default


def _get(d, path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _safe_list(x):
    if isinstance(x, list):
        return x
    if x is None:
        return []
    return [x]


def _derive_regimes(model):
    regimes = set()
    training = model.get("training_data", {})
    compliance_in = model.get("compliance", {})
    domain = (model.get("model_details", {}).get("domain") or "").lower()

    if _bool(training.get("pii")) or "eu" in [j.lower() for j in _safe_list(compliance_in.get("jurisdictions", []))]:
        regimes.add("GDPR")
    if "health" in domain or domain in {"medical", "healthcare"} or training.get("contains_phi"):
        regimes.add("HIPAA")
    if any("children" in str(s).lower() or "minor" in str(s).lower() for s in _safe_list(training.get("sources", []))):
        regimes.add("COPPA")
    for r in _safe_list(compliance_in.get("regimes", [])):
        regimes.add(str(r))
    return sorted(regimes)


def _security_defaults(compliance_in):
    controls = set(_safe_list(compliance_in.get("security_controls", [])))
    base = {
        "encryption_in_transit": True,
        "encryption_at_rest": True,
        "access_control": compliance_in.get("access_control", "RBAC"),
        "audit_logging": True,
        "vulnerability_scanning": True,
        "supply_chain": {
            "sbom": _bool(compliance_in.get("sbom", False)),
            "dependency_pinning": True
        }
    }
    # Normalize known flags from list into booleans
    for flag in ["encryption_in_transit", "encryption_at_rest", "audit_logging"]:
        if flag in controls:
            base[flag] = True
    return base


def _infer_risk_level(model):
    rm = model.get("risk_management", {})
    specified = (rm.get("risk_level") or "").lower()
    domain = (model.get("model_details", {}).get("domain") or "").lower()
    training = model.get("training_data", {})

    if specified in {"low", "medium", "high"}:
        return specified

    # Heuristics
    risk = "low"
    if _bool(training.get("pii")):
        risk = "medium"
    if domain in SAFETY_CRITICAL_DOMAINS:
        risk = "high"
    # Escalate if out-of-scope includes safety-critical activities
    out_of_scope = [str(x).lower() for x in _safe_list(model.get("intended_use", {}).get("out_of_scope", []))]
    if any(token in s for s in out_of_scope for token in ["diagnosis", "clinical", "financial advice", "credit", "autonomous", "weapon", "law enforcement"]):
        risk = "high"
    return risk


def generate_compliance(model: dict) -> dict:
    training = model.get("training_data", {})
    evaluation = model.get("evaluation", {})
    owner = model.get("owner", {})
    compliance_in = model.get("compliance", {})
    model_details = model.get("model_details", {})

    risk_level = _infer_risk_level(model)
    regimes = _derive_regimes(model)
    security_controls = _security_defaults(compliance_in)

    metrics = evaluation.get("metrics") or []
    eval_datasets = evaluation.get("datasets") or []

    compliance = {
        "schema_version": "1.0",
        "generated_at": _now_iso(),
        "model": {
            "id": model.get("id"),
            "name": model.get("name"),
            "version": model.get("version"),
            "domain": model_details.get("domain"),
            "framework": model_details.get("framework"),
            "license": model_details.get("license") or model_details.get("licence")
        },
        "owner": {
            "name": owner.get("name"),
            "email": owner.get("email"),
            "organization": owner.get("org") or owner.get("organization")
        },
        "jurisdictions": compliance_in.get("jurisdictions") or [],
        "regulatory_regimes": regimes,
        "risk_assessment": {
            "level": risk_level,
            "rationale": model.get("risk_management", {}).get("rationale") or "Heuristic assessment derived from domain, PII use, and intended use.",
            "automated_scoring": {
                "pii": _bool(training.get("pii"), False),
                "safety_sensitive_domain": (model_details.get("domain") or "").lower() in SAFETY_CRITICAL_DOMAINS,
                "high_risk_indicators": list(sorted(set([
                    ind for ind, cond in [
                        ("uses_pii", _bool(training.get("pii"), False)),
                        ("safety_critical_domain", (model_details.get("domain") or "").lower() in SAFETY_CRITICAL_DOMAINS),
                        ("missing_evals", len(metrics) == 0)
                    ] if cond
                ])))
            }
        },
        "privacy": {
            "pii": _bool(training.get("pii"), False),
            "contains_phi": _bool(training.get("contains_phi", False), False),
            "data_retention": compliance_in.get("data_retention") or "unspecified",
            "legal_basis": compliance_in.get("legal_basis") or "unspecified",
            "dpa_in_place": _bool(compliance_in.get("dpa", False), False),
            "data_minimization": True,
            "consent_management": _bool(compliance_in.get("consent_management", True), True)
        },
        "security_controls": security_controls,
        "data_governance": {
            "sources": training.get("sources") or [],
            "data_sensitivity": training.get("data_sensitivity") or "unspecified",
            "annotation": training.get("annotation") or "unspecified",
            "license": model_details.get("license") or "unspecified"
        },
        "model_governance": {
            "model_card": True,
            "change_management": {
                "semver": True,
                "changelog": True
            },
            "testing": {
                "eval_datasets": eval_datasets,
                "metrics": metrics,
                "bias_testing": _bool(model.get("risk_management", {}).get("bias_testing", True), True)
            }
        },
        "explainability_transparency": {
            "model_card_url": None,  # filled by service routing, if needed
            "documentation_url": None,
            "user_notifications": _bool(compliance_in.get("user_notifications", True), True)
        },
        "monitoring_incident_response": {
            "monitoring": model.get("deployment", {}).get("monitoring") or "unspecified",
            "incident_contacts": _safe_list(compliance_in.get("incident_contacts", []))
        },
        "audit": {
            "last_audited": None,
            "auditor": None
        },
        "certifications": _safe_list(compliance_in.get("certifications", [])),
        "third_party_dependencies": _safe_list(compliance_in.get("third_party", [])),
        "notes": compliance_in.get("notes") or ""
    }

    return compliance

