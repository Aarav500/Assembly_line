from typing import Dict, Any, List, Tuple
from .models import parse_project, parse_constraints, parse_features, parse_strategy
from .utils import estimate_effort, estimate_risk, normalize, safe_div, topo_sort, dependency_closure, clamp01


def compute_capacity_days(deadline_days: int, team_size: int, budget: float | None) -> Dict[str, float]:
    availability_factor = 0.6  # allocations, meetings, overhead
    person_days_time = max(1.0, deadline_days * team_size * availability_factor)
    assumed_cost_per_person_day = 600.0
    if budget is not None:
        person_days_budget = budget / assumed_cost_per_person_day
        limiting = min(person_days_time, person_days_budget)
        return {
            "capacity_days": float(limiting),
            "time_capacity_days": float(person_days_time),
            "budget_capacity_days": float(person_days_budget),
            "assumed_cost_per_person_day": assumed_cost_per_person_day,
        }
    return {
        "capacity_days": float(person_days_time),
        "time_capacity_days": float(person_days_time),
        "budget_capacity_days": None,
        "assumed_cost_per_person_day": assumed_cost_per_person_day,
    }


def weight_config(bias: str, risk_tolerance: str) -> Dict[str, float]:
    # Weights for score = a*value + b*roi + c*(1-risk) + d*core + e*must
    if bias == "quality":
        a, b, c, d, e = 0.35, 0.20, 0.25, 0.10, 0.10
    elif bias == "cost":
        a, b, c, d, e = 0.35, 0.35, 0.10, 0.10, 0.10
    else:  # time_to_market
        a, b, c, d, e = 0.40, 0.30, 0.10, 0.10, 0.10
    # risk tolerance tunes c
    if risk_tolerance == "low":
        c *= 1.5
    elif risk_tolerance == "high":
        c *= 0.6
    return {"a": a, "b": b, "c": c, "d": d, "e": e}


def rank_and_select(features: List[Dict[str, Any]], constraints: Dict[str, Any], strategy: Dict[str, Any], capacity_days: float) -> Tuple[Dict[str, Any], List[str]]:
    # Precompute normalized fields
    values = [f["value"] for f in features]
    efforts = [f["effort"] for f in features]
    risks = [f["risk"] for f in features]
    norm_value = normalize(values)
    norm_effort = normalize(efforts)
    norm_risk = [clamp01(r / 10.0) for r in risks]

    must_set = set((constraints.get("must_include") or []))
    exclude_set = set((constraints.get("exclude") or []))

    # Graph
    name_to_idx = {f["name"]: i for i, f in enumerate(features)}
    edges = {f["name"]: [d for d in f.get("dependencies", []) if d in name_to_idx] for f in features}

    # Topological sort for warnings
    _, cycles = topo_sort(list(name_to_idx.keys()), edges)
    warnings: List[str] = []
    if cycles:
        warnings.append(f"Dependency cycles detected: {cycles}")

    weights = weight_config(strategy.get("bias", "time_to_market"), strategy.get("risk_tolerance", "medium"))

    scored: List[Dict[str, Any]] = []
    for i, f in enumerate(features):
        roi = safe_div(norm_value[i], (norm_effort[i] + 0.05))  # smooth
        score = (
            weights["a"] * norm_value[i]
            + weights["b"] * roi
            + weights["c"] * (1.0 - norm_risk[i])
            + weights["d"] * (1.0 if f.get("is_core") else 0.0)
            + weights["e"] * (1.0 if f["name"] in must_set else 0.0)
        )
        scored.append({
            **f,
            "norm_value": norm_value[i],
            "norm_effort": norm_effort[i],
            "norm_risk": norm_risk[i],
            "roi": roi,
            "score": score,
            "must": f["name"] in must_set,
            "excluded": f["name"] in exclude_set,
        })

    # Exclude explicitly
    for s in scored:
        if s["excluded"]:
            s["score"] = -1.0

    # Greedy selection honoring dependencies
    remaining_capacity = capacity_days
    selected: Dict[str, Dict[str, Any]] = {}
    reasons: Dict[str, List[str]] = {}

    def add_reason(name: str, text: str):
        reasons.setdefault(name, []).append(text)

    # Ensure must_include first
    must_candidates = [s for s in scored if s["must"] and not s["excluded"]]
    # sort must by dependencies count to ensure deps included
    must_candidates.sort(key=lambda x: len(edges.get(x["name"], [])))

    for m in must_candidates:
        chain = dependency_closure(m["name"], edges)
        chain_effort = sum(scored[name_to_idx[ch]]["effort"] for ch in chain if ch in name_to_idx and ch not in selected)
        if chain_effort <= remaining_capacity:
            for ch in chain:
                if ch not in selected and ch in name_to_idx:
                    selected[ch] = scored[name_to_idx[ch]]
                    add_reason(ch, "Required by must-have or is itself must-have")
            remaining_capacity -= chain_effort
        else:
            warnings.append(f"Must-have '{m['name']}' and its dependencies exceed capacity; partial selection applied if possible.")
            # try to add dependencies first if small
            for ch in chain:
                if ch in selected or ch not in name_to_idx:
                    continue
                eff = scored[name_to_idx[ch]]["effort"]
                if eff <= remaining_capacity:
                    selected[ch] = scored[name_to_idx[ch]]
                    add_reason(ch, "Partial inclusion under capacity for must chain")
                    remaining_capacity -= eff

    # Remaining candidates by score
    candidates = [s for s in scored if s["name"] not in selected and not s["excluded"]]
    candidates.sort(key=lambda x: x["score"], reverse=True)

    for c in candidates:
        chain = dependency_closure(c["name"], edges)
        chain = [x for x in chain if x not in selected and x in name_to_idx]
        chain_effort = sum(scored[name_to_idx[ch]]["effort"] for ch in chain)
        if chain_effort <= remaining_capacity:
            for ch in chain:
                selected[ch] = scored[name_to_idx[ch]]
                # Reasons
                if ch == c["name"]:
                    if c["roi"] >= 0.75:
                        add_reason(ch, "High ROI for MVP timeline")
                    if c.get("is_core"):
                        add_reason(ch, "Core to primary user journey")
                    if c["norm_risk"] <= 0.4:
                        add_reason(ch, "Lower delivery risk fits timeline")
                else:
                    add_reason(ch, f"Dependency required by '{c['name']}'")
            remaining_capacity -= chain_effort
        # else skip if it doesn't fit

    # Prepare outputs
    mvp_features = list(selected.values())

    # Assign non-selected categories
    remaining = [s for s in scored if s["name"] not in selected]
    remaining.sort(key=lambda x: x["score"], reverse=True)
    n = len(remaining)
    cutoff_should = int(max(0, round(n * 0.3)))
    cutoff_could = int(max(0, round(n * 0.8)))
    should = remaining[:cutoff_should]
    could = remaining[cutoff_should:cutoff_could]
    wont = remaining[cutoff_could:]

    # Trade-off reasoning summary
    total_effort = sum(f["effort"] for f in mvp_features)
    total_value = sum(f["value"] for f in mvp_features)
    avg_risk = (sum(f["risk"] for f in mvp_features) / max(1, len(mvp_features))) if mvp_features else 0.0

    global_tradeoffs = []
    if remaining:
        global_tradeoffs.append("Deferred lower ROI or higher risk items to reduce initial time-to-market and delivery risk.")
    if any(f.get("is_core") for f in mvp_features):
        global_tradeoffs.append("Focused on core user journeys to validate product-market fit early.")
    if wont:
        global_tradeoffs.append("Explicitly trimmed non-essential scope to protect schedule and quality.")

    # Construct reasoning per excluded
    for s in remaining:
        rlist: List[str] = []
        if s["excluded"]:
            rlist.append("Explicitly excluded by constraints")
        if s["roi"] < 0.4:
            rlist.append("Low ROI vs MVP goals")
        if s["norm_risk"] > 0.6:
            rlist.append("Higher delivery risk under current constraints")
        if s["effort"] > remaining_capacity:
            rlist.append("Insufficient remaining capacity")
        if not rlist:
            rlist.append("Scheduled for later iteration based on priority scoring")
        reasons[s["name"]] = rlist

    # MVP order proposal: topological order filtered to selected, tie-broken by score
    order, _ = topo_sort([f["name"] for f in scored], edges)
    score_map = {f["name"]: f["score"] for f in scored}
    mvp_names = set(selected.keys())
    ordered_mvp = [n for n in order if n in mvp_names]
    # within same topo layer not handled; simple stable sort by score descending preserving topo order blocks
    ordered_mvp = sorted(ordered_mvp, key=lambda n: score_map.get(n, 0.0), reverse=True)

    result = {
        "mvp": {
            "features": [summarize_feature(f, reasons) for f in mvp_features],
            "effort_total_days": round(total_effort, 2),
            "value_total": round(total_value, 2),
            "avg_risk": round(avg_risk, 2),
            "remaining_capacity_days": round(remaining_capacity, 2),
            "proposed_implementation_order": ordered_mvp,
        },
        "backlog": {
            "should": [summarize_feature(f, reasons) for f in should],
            "could": [summarize_feature(f, reasons) for f in could],
            "wont": [summarize_feature(f, reasons) for f in wont],
        },
        "warnings": list(set(warnings)),
        "reasoning": {
            "global": global_tradeoffs,
        },
    }
    return result, [r for r in warnings]


def summarize_feature(f: Dict[str, Any], reasons: Dict[str, List[str]]) -> Dict[str, Any]:
    return {
        "name": f.get("name"),
        "value": f.get("value"),
        "effort_days": f.get("effort"),
        "risk": f.get("risk"),
        "roi_score": round(float(f.get("roi", 0.0)), 3),
        "priority_score": round(float(f.get("score", 0.0)), 3),
        "is_core": bool(f.get("is_core", False)),
        "must": bool(f.get("must", False)),
        "dependencies": list(f.get("dependencies", []) or []),
        "reasons": reasons.get(f.get("name"), []),
    }


def suggest_scope(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")

    project = parse_project(payload.get("project", {}) or {})
    constraints = parse_constraints(payload.get("constraints", {}) or {})
    strategy = parse_strategy(payload.get("strategy", {}) or {})
    features_in = parse_features(payload.get("features", []) or [])

    if not features_in:
        raise ValueError("No features provided")

    # Build feature dicts with estimated fields
    features: List[Dict[str, Any]] = []
    missing_deps: List[str] = []
    names = {f.name for f in features_in}
    for f in features_in:
        effort = f.effort if f.effort is not None else estimate_effort(f.description)
        risk = f.risk if f.risk is not None else estimate_risk(f.description)
        value = f.value if f.value is not None else 5.0
        deps = [d for d in (f.dependencies or []) if isinstance(d, str)]
        for d in deps:
            if d not in names:
                missing_deps.append(f"Feature '{f.name}' references missing dependency '{d}'")
        features.append({
            "name": f.name,
            "description": f.description,
            "value": float(value),
            "effort": float(effort),
            "risk": float(risk),
            "dependencies": deps,
            "is_core": bool(f.is_core),
            "tags": list(f.tags or []),
        })

    cap = compute_capacity_days(project.deadline_days, project.team.size, project.budget)

    ranked, warnings = rank_and_select(features, constraints.__dict__, strategy.__dict__, cap["capacity_days"])

    header = {
        "project": {
            "name": project.name,
            "goal": project.goal,
            "deadline_days": project.deadline_days,
            "team_size": project.team.size,
            "budget": project.budget,
            "assumed_availability_factor": 0.6,
        },
        "strategy": strategy.__dict__,
        "constraints": constraints.__dict__,
        "capacity": cap,
    }

    out = {
        "summary": header,
        **ranked,
    }
    all_warnings = list(set((warnings or []) + (missing_deps or [])))
    if all_warnings:
        out["warnings"] = all_warnings

    # Trade-off statement
    out["reasoning"]["tradeoff_statement"] = _compose_tradeoff_statement(header, ranked)

    return out


def _compose_tradeoff_statement(header: Dict[str, Any], ranked: Dict[str, Any]) -> str:
    proj = header.get("project", {})
    cap = header.get("capacity", {})
    mvp = ranked.get("mvp", {})
    eff = mvp.get("effort_total_days", 0)
    rem = mvp.get("remaining_capacity_days", 0)
    bias = header.get("strategy", {}).get("bias", "time_to_market")
    rt = header.get("strategy", {}).get("risk_tolerance", "medium")
    parts = []
    parts.append(
        f"With a team of {proj.get('team_size')} over {proj.get('deadline_days')} days, estimated capacity is {round(cap.get('capacity_days', 0), 1)} person-days."
    )
    parts.append(
        f"The proposed MVP consumes {round(eff,1)} person-days, leaving ~{round(rem,1)} for buffer, polish, or contingencies."
    )
    parts.append(
        f"Prioritization emphasizes {bias.replace('_',' ')} with {rt} risk tolerance, selecting high-ROI, core features and deferring higher-risk/effort items."
    )
    return " ".join(parts)


def sample_payload() -> Dict[str, Any]:
    return {
        "project": {
            "name": "Team Hub",
            "description": "Internal collaboration tool for small teams with chat, tasks, and file sharing.",
            "goal": "Validate core usage and retention within 6 weeks.",
            "deadline_days": 42,
            "budget": 30000,
            "team": {"size": 3, "skills": ["backend", "frontend", "devops"]},
        },
        "strategy": {"bias": "time_to_market", "risk_tolerance": "medium"},
        "constraints": {
            "must_include": ["Auth", "Core Chat"],
            "exclude": ["Mobile App"],
            "non_functional": ["security", "observability"],
        },
        "features": [
            {
                "name": "Auth",
                "description": "Email/password login with password reset and basic role-based authorization (admin, user).",
                "value": 9,
                "effort": 6,
                "risk": 3,
                "dependencies": [],
                "is_core": True,
            },
            {
                "name": "Core Chat",
                "description": "Real-time team channels with mentions and message history using websockets.",
                "value": 9,
                "effort": 9,
                "risk": 5,
                "dependencies": ["Auth"],
                "is_core": True,
            },
            {
                "name": "File Sharing",
                "description": "Upload/download files with previews, virus scanning, and S3 integration.",
                "value": 7,
                "effort": 7,
                "risk": 5,
                "dependencies": ["Auth"],
                "is_core": False,
            },
            {
                "name": "Task Boards",
                "description": "Kanban boards with drag-and-drop and due date reminders.",
                "value": 8,
                "effort": 8,
                "risk": 4,
                "dependencies": ["Auth"],
                "is_core": True,
            },
            {
                "name": "Search",
                "description": "Search across messages and files with highlighting.",
                "value": 7,
                "effort": 6,
                "risk": 4,
                "dependencies": ["Auth"],
                "is_core": False,
            },
            {
                "name": "Mobile App",
                "description": "Native iOS and Android apps with push notifications.",
                "value": 6,
                "effort": 18,
                "risk": 6,
                "dependencies": ["Core Chat"],
                "is_core": False,
            },
            {
                "name": "SSO",
                "description": "OAuth2 / SAML SSO with Google and Microsoft integration.",
                "value": 6,
                "effort": 7,
                "risk": 6,
                "dependencies": ["Auth"],
                "is_core": False,
            },
            {
                "name": "Analytics Dashboard",
                "description": "Usage KPIs with charts and weekly email reports.",
                "value": 5,
                "effort": 5,
                "risk": 3,
                "dependencies": ["Auth"],
                "is_core": False,
            },
        ],
    }

