import math
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Set

# ----------------------------
# Text utilities
# ----------------------------

def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _tokenize(val) -> Set[str]:
    tokens: Set[str] = set()
    if val is None:
        return tokens
    if isinstance(val, str):
        s = _norm(val)
        for t in re.split(r"[^a-z0-9\+]+", s):
            if t:
                tokens.add(t)
    elif isinstance(val, (list, tuple, set)):
        for x in val:
            tokens |= _tokenize(x)
    else:
        tokens |= _tokenize(str(val))
    return tokens


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ----------------------------
# Date utilities
# ----------------------------

def _parse_date_iso(d: str):
    if not d:
        return None
    try:
        return datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _is_past_deadline(deadline_iso: str) -> bool:
    dt = _parse_date_iso(deadline_iso)
    if not dt:
        return False
    return dt < datetime.now(timezone.utc)


# ----------------------------
# Preprocess opportunities
# ----------------------------

def preprocess_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepped = []
    for op in opportunities:
        op2 = dict(op)
        # Canonical fields
        op2["_sectors_tokens"] = _tokenize(op.get("sectors", []))
        op2["_stages_tokens"] = _tokenize(op.get("stages", []))
        thesis_tokens = _tokenize(op.get("thesis_keywords", [])) | _tokenize(op.get("tags", [])) | _tokenize(op.get("description", ""))
        op2["_thesis_tokens"] = thesis_tokens
        op2["_locations_tokens"] = _tokenize(op.get("locations", []))
        op2["_type"] = _norm(op.get("type", ""))
        op2["_deadline_past"] = _is_past_deadline(op.get("deadline"))
        # Normalize requirement flags to booleans or None
        req = op.get("requirements", {}) or {}
        norm_req = {
            "female_founder": req.get("female_founder"),
            "minority_owned": req.get("minority_owned"),
            "veteran": req.get("veteran"),
            "student": req.get("student"),
            "university_affiliated": req.get("university_affiliated"),
            "nonprofit_only": req.get("nonprofit_only"),
            "for_profit_only": req.get("for_profit_only"),
            "climate_focus": req.get("climate_focus"),
            "impact_focus": req.get("impact_focus"),
        }
        op2["_requirements"] = norm_req
        prepped.append(op2)
    return prepped


# ----------------------------
# Scoring logic
# ----------------------------

WEIGHTS = {
    "sector": 0.35,
    "stage": 0.20,
    "location": 0.15,
    "thesis": 0.20,
    "amount": 0.10,
}


_ALLOWED_TYPES = {"investor", "grant", "accelerator"}


def _bool_or_none(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = _norm(str(v))
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def _get_amount_range(op: Dict[str, Any]) -> Tuple[float, float]:
    # Returns (min, max) USD-equivalent as floats if provided; else (0, 0)
    check_size = op.get("check_size") or {}
    grant_amount = op.get("grant_amount") or {}
    min_val = float(check_size.get("min") or grant_amount.get("min") or 0)
    max_val = float(check_size.get("max") or grant_amount.get("max") or 0)
    if min_val and not max_val:
        max_val = min_val
    if max_val and not min_val:
        min_val = 0.0
    return (min_val, max_val)


def _amount_score(amount_needed: float, op: Dict[str, Any]) -> float:
    if not amount_needed:
        return 0.5  # neutral if startup doesn't specify
    a_min, a_max = _get_amount_range(op)
    if a_min == 0 and a_max == 0:
        return 0.5  # unknown, neutral
    # Within range => good, else distance-based decay
    if a_min <= amount_needed <= a_max:
        return 1.0
    # Outside range: compute distance ratio
    center = (a_min + a_max) / 2 if (a_min or a_max) else amount_needed
    spread = max(a_max - a_min, 1.0)
    dist = abs(amount_needed - center) / spread
    # Map via exp decay
    return math.exp(-dist)


def _stage_score(stage: str, op: Dict[str, Any]) -> float:
    if not stage:
        return 0.5
    st = _tokenize(stage)
    has = op.get("_stages_tokens", set())
    return 1.0 if (st & has) else 0.0


def _location_score(location: str, op: Dict[str, Any]) -> float:
    loc_tokens = _tokenize(location)
    allowed = op.get("_locations_tokens", set())
    if "global" in allowed or "remote" in allowed:
        return 1.0
    return 1.0 if (loc_tokens & allowed) else 0.0


def _constraints_check(profile: Dict[str, Any], op: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    req = op.get("_requirements", {})

    prof = {
        "female_founder": _bool_or_none(profile.get("female_founder")),
        "minority_owned": _bool_or_none(profile.get("minority_owned")),
        "veteran": _bool_or_none(profile.get("veteran")),
        "student": _bool_or_none(profile.get("student")),
        "university_affiliated": _bool_or_none(profile.get("university_affiliated")),
        "nonprofit": _bool_or_none(profile.get("nonprofit")),
        "for_profit": _bool_or_none(profile.get("for_profit")),
        "climate": _bool_or_none(profile.get("climate")),
        "impact": _bool_or_none(profile.get("impact")),
    }

    # Hard constraints
    if req.get("nonprofit_only") is True and not prof.get("nonprofit"):
        return False, ["Nonprofit-only opportunity"]
    if req.get("for_profit_only") is True and not prof.get("for_profit"):
        return False, ["For-profit-only opportunity"]

    # If a requirement is explicitly True, the profile must match
    for flag in ["female_founder", "minority_owned", "veteran", "student", "university_affiliated", "climate_focus", "impact_focus"]:
        if req.get(flag) is True and not prof.get(flag.split("_")[0]):
            label = flag.replace("_", " ")
            return False, [f"Requires {label}"]

    # Soft notes
    if req.get("female_founder") is True and prof.get("female"):
        reasons.append("Female founder preference match")

    return True, reasons


def _deadline_penalty(op: Dict[str, Any]) -> float:
    # Past deadline: significant penalty for grants/accelerators; moderate for investors
    if not op.get("deadline"):
        return 1.0
    if not op.get("_deadline_past"):
        return 1.0
    t = op.get("_type")
    if t in {"grant", "accelerator"}:
        return 0.0  # fully ineligible
    return 0.6  # investors seldom have hard deadlines


def _type_filter(profile: Dict[str, Any], t: str) -> bool:
    # Optional filter by allowed types in profile["want_types"]
    want = profile.get("want_types")
    if not want:
        return True
    tokens = {w.strip().lower() for w in want if isinstance(w, str)}
    return t in tokens


def _build_reason_list(profile: Dict[str, Any], op: Dict[str, Any], subscores: Dict[str, float]) -> List[str]:
    reasons = []
    if subscores.get("sector", 0) > 0:
        reasons.append("Sector fit")
    if subscores.get("stage", 0) > 0:
        reasons.append("Stage match")
    if subscores.get("location", 0) > 0:
        reasons.append("Location eligible")
    if subscores.get("thesis", 0) > 0:
        reasons.append("Thesis/keyword alignment")
    if subscores.get("amount", 0) > 0.7:
        reasons.append("Funding amount fits")
    if op.get("_deadline_past") and op.get("deadline"):
        reasons.append("Past deadline (reduced priority)")
    return reasons


def match_startup(profile: Dict[str, Any], opportunities: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Normalize profile tokens
    p_sectors = _tokenize(profile.get("sectors") or profile.get("sector"))
    p_tags = _tokenize(profile.get("tags")) | _tokenize(profile.get("description"))
    p_stage = (profile.get("stage") or "").strip().lower()
    p_location = (profile.get("location") or "").strip().lower()
    amount_needed = None
    try:
        if profile.get("amount_needed") is not None:
            amount_needed = float(profile.get("amount_needed"))
    except Exception:
        amount_needed = None

    results: List[Dict[str, Any]] = []

    for op in opportunities:
        t = op.get("_type")
        if t not in _ALLOWED_TYPES:
            continue
        if not _type_filter(profile, t):
            continue

        # Constraints
        eligible, constraint_reasons = _constraints_check(profile, op)
        if not eligible:
            continue

        # Subscores
        sector_score = _jaccard(p_sectors, op.get("_sectors_tokens", set()))
        stage_score = _stage_score(p_stage, op)
        location_score = _location_score(p_location, op)
        thesis_score = _jaccard(p_tags, op.get("_thesis_tokens", set()))
        amount_score = _amount_score(amount_needed, op)

        subs = {
            "sector": sector_score,
            "stage": stage_score,
            "location": location_score,
            "thesis": thesis_score,
            "amount": amount_score,
        }

        base = sum(WEIGHTS[k] * subs[k] for k in WEIGHTS)
        penalty = _deadline_penalty(op)
        total = max(0.0, min(1.0, base * penalty))

        reasons = _build_reason_list(profile, op, subs) + constraint_reasons

        results.append({
            "id": op.get("id"),
            "name": op.get("name"),
            "type": t,
            "score": round(total * 100, 2),
            "reasons": reasons,
            "website": op.get("website"),
            "deadline": op.get("deadline"),
            "stages": op.get("stages", []),
            "sectors": op.get("sectors", []),
            "locations": op.get("locations", []),
            "tags": op.get("tags", []),
            "check_size": op.get("check_size"),
            "grant_amount": op.get("grant_amount"),
            "equity_required": op.get("equity_required"),
        })

    # Group by type
    by_type = {"investors": [], "grants": [], "accelerators": []}
    for r in results:
        if r["type"] == "investor":
            by_type["investors"].append(r)
        elif r["type"] == "grant":
            by_type["grants"].append(r)
        elif r["type"] == "accelerator":
            by_type["accelerators"].append(r)

    # Sort each bucket by score desc
    for k in by_type:
        by_type[k] = sorted(by_type[k], key=lambda x: x["score"], reverse=True)

    # Top-level also include all combined
    combined = sorted(results, key=lambda x: x["score"], reverse=True)

    return {
        "results": combined,
        "investors": by_type["investors"],
        "grants": by_type["grants"],
        "accelerators": by_type["accelerators"],
        "count": {
            "total": len(combined),
            "investors": len(by_type["investors"]),
            "grants": len(by_type["grants"]),
            "accelerators": len(by_type["accelerators"]),
        },
    }

