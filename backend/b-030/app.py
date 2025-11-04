import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Any

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


@dataclass
class CarbonInputs:
    daily_users: int = 1000
    requests_per_user: float = 5.0
    uses_ml: bool = False
    model_size: str = "none"  # none|small|medium|large
    data_per_user_mb: float = 50.0  # MB per user stored
    retention_months: int = 12
    data_per_request_mb: float = 1.0
    pue: float = 1.4  # power usage effectiveness
    grid_intensity_kg_per_kwh: float = 0.475  # kgCO2e per kWh
    renewable_offset: float = 0.0  # 0..1
    user_base_multiplier: float = 3.0  # DAU -> total users approx


def to_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in {"1", "true", "yes", "on"}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def safe_float(val: Any, default: float) -> float:
    try:
        return float(val)
    except Exception:
        return float(default)


def safe_int(val: Any, default: int) -> int:
    try:
        return int(float(val))
    except Exception:
        return int(default)


# --------------------------- Text Analyses ---------------------------

PRIVACY_KEYWORDS = {
    "pii": [
        r"social security|ssn",
        r"driver'?s license|dl number",
        r"passport",
        r"biometric|face recognition|fingerprint|iris|voiceprint",
        r"camera|microphone|keylogger",
        r"gps|location|geofence|geolocation",
        r"cookie|tracker|advertising id|idfa|gaid",
        r"health|medical|hipaa",
        r"financial|credit card|bank|iban|swift|account number",
        r"email|phone|contact list",
        r"ip address",
        r"children|minor|child|age under",
    ],
    "handling": [
        r"collect|harvest|scrape",
        r"store|retain",
        r"share|sell|broker|third[- ]party",
        r"profil(e|ing)|target(ed|ing)",
        r"consent|opt[- ]in|opt[- ]out",
        r"encrypt|anonymi[sz]e|pseudonymi[sz]e",
        r"gdpr|ccpa|coppa|sox|ferpa",
    ],
}

BIAS_KEYWORDS = {
    "ai": [r"ai|ml|algorithm|model|classifier|neural|gpt|llm|recommend(er|ation)", r"automated|scoring|ranking"],
    "protected": [
        r"race|racial|ethnic|ethnicity",
        r"gender|sex|female|male|nonbinary|trans",
        r"age|young|old|senior|elder",
        r"religion|faith|muslim|christian|jewish|hindu|buddhist",
        r"disab(ility|led)|wheelchair|blind|deaf",
        r"pregnan(t|cy)|marital",
        r"lgbt|orientation",
    ],
    "domain": [
        r"hiring|recruit|promotion|hr",
        r"credit|loan|lending|underwriting|insurance|premium",
        r"police|policing|surveillance|risk score|recidivism",
        r"housing|tenant|landlord",
        r"education|admissions|grading",
        r"health|medical|diagnosis",
        r"ads|advertis(ing|ement)|content moderation",
    ],
}

KEYWORD_COMPILED = {k: [re.compile(p, re.I) for p in v] for k, v in {**PRIVACY_KEYWORDS, **BIAS_KEYWORDS}.items()}


def find_matches(text: str, patterns: List[re.Pattern]) -> List[str]:
    found = []
    for pat in patterns:
        if pat.search(text or ""):
            found.append(pat.pattern)
    return found


def analyze_privacy(text: str, inputs: CarbonInputs) -> Dict[str, Any]:
    t = text or ""
    matches_pii = find_matches(t, KEYWORD_COMPILED["pii"])
    matches_handling = find_matches(t, KEYWORD_COMPILED["handling"])

    score = 10
    notes = []

    # Sensitivity boosts
    sensitivity_boosts = {
        r"biometric": 35,
        r"health|medical|hipaa": 25,
        r"financial|credit card|bank": 25,
        r"children|minor|coppa": 30,
        r"gps|location|geoloc": 15,
    }
    for pat, boost in sensitivity_boosts.items():
        if re.search(pat, t, re.I):
            score += boost
            notes.append(f"Sensitive data indicated: {pat}")

    # Handling risks
    if re.search(r"share|sell|third[- ]party|broker", t, re.I):
        score += 20
        notes.append("Third-party sharing/selling suggested")
    if re.search(r"collect|harvest|scrape", t, re.I):
        score += 8
    if re.search(r"store|retain", t, re.I):
        # storage volume proxy
        est_gb = (inputs.daily_users * inputs.user_base_multiplier) * (inputs.data_per_user_mb / 1024.0)
        if est_gb > 1000:
            score += 10
            notes.append("Large data retention indicated")
        else:
            score += 5
    if re.search(r"encrypt|anonymi[sz]e|pseudonymi[sz]e", t, re.I):
        score -= 8
        notes.append("Mitigations noted (encryption/anonymization)")
    if re.search(r"consent|opt[- ]in|opt[- ]out", t, re.I):
        score -= 5
        notes.append("User consent mechanisms referenced")

    # Clamp score
    score = clamp(score, 0, 100)

    # Risk level from score and domain context
    if score >= 67:
        risk = "high"
    elif score >= 34:
        risk = "medium"
    else:
        risk = "low"

    mitigations = [
        "Map data flows; collect only what is necessary (data minimization)",
        "Obtain explicit, informed consent; provide opt-out where appropriate",
        "Encrypt data in transit and at rest; implement key management",
        "Use anonymization/pseudonymization for analytics and model training",
        "Limit retention periods; implement deletion and subject access processes",
        "Avoid selling/sharing personal data; vet third parties with DPAs",
        "Run a DPIA/PIA if handling sensitive or large-scale personal data",
        "Comply with applicable regulations (GDPR/CCPA/COPPA/HIPAA)",
        "Implement role-based access controls and audit logging",
    ]

    return {
        "score": round(score, 1),
        "risk_level": risk,
        "flags": {
            "pii_indicators": matches_pii,
            "handling_indicators": matches_handling,
        },
        "notes": notes,
        "mitigations": mitigations,
    }


def analyze_bias(text: str, inputs: CarbonInputs) -> Dict[str, Any]:
    t = text or ""
    ai = bool(find_matches(t, [re.compile(p, re.I) for p in BIAS_KEYWORDS["ai"]])) or inputs.uses_ml
    protected = find_matches(t, [re.compile(p, re.I) for p in BIAS_KEYWORDS["protected"]])
    domain = find_matches(t, [re.compile(p, re.I) for p in BIAS_KEYWORDS["domain"]])

    score = 10
    notes = []
    if ai:
        score += 20
        notes.append("Automated decision-making/ML suggested")
    if protected:
        score += 20
        notes.append("References to protected characteristics")
    if domain:
        # higher weight if high-stakes
        high_stakes = re.search(
            r"hiring|credit|loan|insurance|police|housing|health|medical|admissions|grading|underwriting|recidivism",
            t,
            re.I,
        )
        if high_stakes:
            score += 30
            notes.append("High-stakes domain indicated")
        else:
            score += 15
            notes.append("Potentially sensitive domain indicated")

    # Mitigations recognized
    if re.search(r"audit|bias testing|fair(ness|ly)|debias|explainable|interpretable|human in the loop", t, re.I):
        score -= 10
        notes.append("Fairness/audit mitigations referenced")

    score = clamp(score, 0, 100)
    if score >= 67:
        risk = "high"
    elif score >= 34:
        risk = "medium"
    else:
        risk = "low"

    mitigations = [
        "Assess impact and define fairness goals relevant to context",
        "Use representative, high-quality data; document data lineage",
        "Perform pre-/post-deployment bias testing and subgroup analysis",
        "Adopt human-in-the-loop oversight for consequential decisions",
        "Provide explanations and contestability for decisions",
        "Monitor for drift; retrain and revalidate periodically",
        "Avoid using protected attributes or close proxies in models",
        "Perform accessibility and inclusive design reviews",
    ]

    return {
        "score": round(score, 1),
        "risk_level": risk,
        "flags": {
            "ai_indicators": ai,
            "protected_indicators": protected,
            "domain_indicators": domain,
        },
        "notes": notes,
        "mitigations": mitigations,
    }


# --------------------------- Carbon Analysis ---------------------------

def kwh_per_request(model_size: str) -> float:
    mapping = {
        "none": 0.00005,  # simple web request baseline
        "small": 0.0005,  # small ML model
        "medium": 0.005,  # medium model
        "large": 0.05,  # large model / LLM
    }
    return mapping.get(model_size, mapping["none"])


def compute_carbon(inputs: CarbonInputs) -> Dict[str, Any]:
    # Assumptions
    storage_energy_kwh_per_gb_month = 1.2
    network_energy_kwh_per_gb = 0.06

    daily_requests = inputs.daily_users * inputs.requests_per_user

    # Compute energy
    kwh_req = kwh_per_request(inputs.model_size if inputs.uses_ml else "none")
    inference_kwh_daily = daily_requests * kwh_req

    network_gb_daily = (daily_requests * inputs.data_per_request_mb) / 1024.0
    network_kwh_daily = network_gb_daily * network_energy_kwh_per_gb

    # Storage energy (estimate total users from DAU)
    est_total_users = inputs.daily_users * inputs.user_base_multiplier
    storage_gb_total = (est_total_users * inputs.data_per_user_mb) / 1024.0
    storage_kwh_monthly = storage_gb_total * storage_energy_kwh_per_gb_month

    # Annualize and account for PUE
    compute_kwh_annual = (inference_kwh_daily + network_kwh_daily) * 365.0 * inputs.pue
    storage_kwh_annual = storage_kwh_monthly * 12.0 * inputs.pue
    total_kwh_annual = compute_kwh_annual + storage_kwh_annual

    # Emissions
    effective_intensity = inputs.grid_intensity_kg_per_kwh * (1.0 - clamp(inputs.renewable_offset, 0.0, 1.0))
    total_kg_co2e_annual = total_kwh_annual * effective_intensity

    # Per-user metrics
    kg_per_user_year = total_kg_co2e_annual / max(est_total_users, 1)

    # Risk bands by total annual emissions
    if total_kg_co2e_annual < 5000:  # <5 tCO2e
        risk = "low"
    elif total_kg_co2e_annual < 50000:  # 5-50 tCO2e
        risk = "medium"
    else:
        risk = "high"

    recommendations = [
        "Choose low-carbon regions and providers; increase renewable procurement",
        "Reduce model size (distillation/quantization); cache results where possible",
        "Batch requests; use efficient serving hardware; autoscale to avoid idle",
        "Minimize data transfer (compression, CDNs); edge caching",
        "Reduce stored data volume and retention; delete stale data",
        "Optimize PUE by using efficient data centers; avoid overprovisioning",
    ]

    return {
        "annual_kwh": round(total_kwh_annual, 3),
        "annual_kgco2e": round(total_kg_co2e_annual, 3),
        "per_user_kgco2e_year": round(kg_per_user_year, 4),
        "risk_level": risk,
        "breakdown": {
            "compute_kwh_annual": round(compute_kwh_annual, 3),
            "storage_kwh_annual": round(storage_kwh_annual, 3),
            "network_kwh_daily": round(network_kwh_daily, 6),
            "inference_kwh_daily": round(inference_kwh_daily, 6),
            "storage_gb_total": round(storage_gb_total, 3),
            "daily_requests": int(daily_requests),
            "pue": inputs.pue,
        },
        "assumptions": {
            "kwh_per_request": kwh_req,
            "storage_energy_kwh_per_gb_month": storage_energy_kwh_per_gb_month,
            "network_energy_kwh_per_gb": network_energy_kwh_per_gb,
            "grid_intensity_kg_per_kwh": inputs.grid_intensity_kg_per_kwh,
            "renewable_offset": clamp(inputs.renewable_offset, 0.0, 1.0),
            "user_base_multiplier": inputs.user_base_multiplier,
        },
        "recommendations": recommendations,
    }


def analyze_idea(text: str, inputs: CarbonInputs) -> Dict[str, Any]:
    privacy = analyze_privacy(text, inputs)
    bias = analyze_bias(text, inputs)
    carbon = compute_carbon(inputs)

    # Overall: prioritize max risk
    risk_order = {"low": 0, "medium": 1, "high": 2}
    overall_level = max([privacy["risk_level"], bias["risk_level"], carbon["risk_level"]], key=lambda r: risk_order.get(r, 0))

    return {
        "privacy": privacy,
        "bias": bias,
        "carbon": carbon,
        "overall": {
            "risk_level": overall_level,
            "summary": "Overall risk equals the highest among privacy, bias, and carbon dimensions",
        },
        "disclaimer": (
            "This tool provides heuristic estimates for planning and risk discovery. "
            "It is not legal, compliance, or environmental accounting advice."
        ),
    }


# --------------------------- Flask Routes ---------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    form_defaults = {
        "idea_text": request.form.get("idea_text", ""),
        "daily_users": request.form.get("daily_users", "1000"),
        "requests_per_user": request.form.get("requests_per_user", "5"),
        "uses_ml": request.form.get("uses_ml", ""),
        "model_size": request.form.get("model_size", "none"),
        "data_per_user_mb": request.form.get("data_per_user_mb", "50"),
        "retention_months": request.form.get("retention_months", "12"),
        "data_per_request_mb": request.form.get("data_per_request_mb", "1"),
        "pue": request.form.get("pue", "1.4"),
        "grid_intensity": request.form.get("grid_intensity", "0.475"),
        "renewable_offset": request.form.get("renewable_offset", "0"),
        "user_base_multiplier": request.form.get("user_base_multiplier", "3"),
    }

    if request.method == "POST":
        idea_text = request.form.get("idea_text", "")

        # Grid intensity selection: allow preset names or numeric
        grid_sel = request.form.get("grid_intensity", "0.475").strip()
        grid_map = {"global": 0.475, "low": 0.2, "high": 0.8}
        gi = grid_map.get(grid_sel, safe_float(grid_sel, 0.475))

        inputs = CarbonInputs(
            daily_users=safe_int(request.form.get("daily_users"), 1000),
            requests_per_user=safe_float(request.form.get("requests_per_user"), 5.0),
            uses_ml=to_bool(request.form.get("uses_ml")),
            model_size=request.form.get("model_size", "none"),
            data_per_user_mb=safe_float(request.form.get("data_per_user_mb"), 50.0),
            retention_months=safe_int(request.form.get("retention_months"), 12),
            data_per_request_mb=safe_float(request.form.get("data_per_request_mb"), 1.0),
            pue=safe_float(request.form.get("pue"), 1.4),
            grid_intensity_kg_per_kwh=gi,
            renewable_offset=clamp(safe_float(request.form.get("renewable_offset"), 0.0) / 100.0, 0.0, 1.0),
            user_base_multiplier=safe_float(request.form.get("user_base_multiplier"), 3.0),
        )
        result = analyze_idea(idea_text, inputs)

    return render_template("index.html", result=result, form=form_defaults)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    idea_text = data.get("idea_text", "")

    # Grid intensity
    grid_sel = str(data.get("grid_intensity", 0.475)).strip()
    grid_map = {"global": 0.475, "low": 0.2, "high": 0.8}
    gi = grid_map.get(grid_sel, safe_float(grid_sel, 0.475))

    inputs = CarbonInputs(
        daily_users=safe_int(data.get("daily_users"), 1000),
        requests_per_user=safe_float(data.get("requests_per_user"), 5.0),
        uses_ml=to_bool(data.get("uses_ml")),
        model_size=str(data.get("model_size", "none")),
        data_per_user_mb=safe_float(data.get("data_per_user_mb"), 50.0),
        retention_months=safe_int(data.get("retention_months"), 12),
        data_per_request_mb=safe_float(data.get("data_per_request_mb"), 1.0),
        pue=safe_float(data.get("pue"), 1.4),
        grid_intensity_kg_per_kwh=gi,
        renewable_offset=clamp(safe_float(data.get("renewable_offset"), 0.0), 0.0, 1.0),
        user_base_multiplier=safe_float(data.get("user_base_multiplier"), 3.0),
    )

    analysis = analyze_idea(idea_text, inputs)
    return jsonify({"inputs": asdict(inputs), "analysis": analysis})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app
