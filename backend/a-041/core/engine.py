from dataclasses import dataclass
from typing import Dict, List, Any, Tuple

from .rules import FEATURE_RULES, DEFAULT_PLAN_SHELLS, SUPPORTED_COST_KEYS, DEFAULT_COGS, MARGIN_TARGET_DEFAULT, DEFAULT_USAGE_BY_PLAN, ADD_ON_LIBRARY
from .utils import clamp, pct, safe_get, sum_costs, merge_costs


@dataclass
class Context:
    detected: Dict[str, Any]
    metrics: Dict[str, Any]
    constraints: Dict[str, Any]
    existing_plans: List[Dict[str, Any]]


def suggest(payload: Dict[str, Any]) -> Dict[str, Any]:
    detected = payload.get("detected", {}) or {}
    metrics = payload.get("metrics", {}) or {}
    constraints = payload.get("constraints", {}) or {}
    existing_plans = payload.get("existing_plans", []) or []

    ctx = Context(detected=detected, metrics=metrics, constraints=constraints, existing_plans=existing_plans)

    features = set((detected.get("functionalities") or []))
    if not isinstance(features, set):
        features = set(features)

    patterns, rationales, add_on_keys = _derive_patterns(features)
    value_metrics = _select_value_metrics(features, detected)

    cost_table = merge_costs(DEFAULT_COGS, metrics.get("cogs_per_unit"))
    margin_target = constraints.get("margin_target", MARGIN_TARGET_DEFAULT)
    currency = constraints.get("currency", "USD")

    unit_prices = _compute_unit_prices(cost_table, margin_target)

    price_hints = _compute_price_hints(ctx, unit_prices, margin_target)

    plans = _build_plans(ctx, features, value_metrics, unit_prices, price_hints, currency)

    add_ons = _build_add_ons(add_on_keys, unit_prices, currency)

    experiments = _propose_experiments(features, value_metrics)

    confidence = _confidence(features, value_metrics, patterns)

    pricing_models = sorted(list(set(patterns.get("pricing_models", []))))

    result = {
        "pricing_models": pricing_models,
        "value_metrics": value_metrics,
        "unit_prices": {**unit_prices, "currency": currency},
        "plan_templates": plans,
        "add_ons": add_ons,
        "experiments": experiments,
        "rationales": rationales,
        "confidence": round(confidence, 3)
    }
    return result


def _derive_patterns(features: set) -> Tuple[Dict[str, Any], List[str], List[str]]:
    pricing_models = []
    plan_gates = []
    rationales = []
    add_on_keys = []

    for f in features:
        rule = FEATURE_RULES.get(f)
        if not rule:
            continue
        pricing_models.extend(rule.get("pricing_models", []))
        plan_gates.extend(rule.get("plan_gates", []))
        rationales.append(f"{f}: {rule.get('rationale')}")
        add_on_keys.extend(rule.get("add_ons", []))

    return {"pricing_models": pricing_models, "plan_gates": plan_gates}, rationales, list(set(add_on_keys))


def _select_value_metrics(features: set, detected: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = []

    def add(metric: str, rationale: str, weight: float):
        candidates.append({"metric": metric, "rationale": rationale, "confidence": clamp(weight, 0.0, 1.0)})

    if "real_time_collaboration" in features or "role_based_access" in features:
        add("seats", "Team value scales with user count; aligns revenue to adoption.", 0.9)
        add("active_users", "Active user gating can discourage shelfware and map to realized value.", 0.6)

    if "api_access" in features:
        add("api_calls", "Clean metering for developer usage tiers and overages.", 0.95)
        add("keys_per_account", "Gate number of API keys to differentiate plans.", 0.5)

    if "ai_generation" in features:
        add("ai_tokens", "Token-based metering correlates with inference cost and value.", 0.95)
        add("gpu_minutes", "GPU runtime metering for custom or heavy models.", 0.7)

    if "analytics_dashboard" in features:
        add("dashboards", "Gate number of dashboards/reports by tier.", 0.6)

    if "marketplace" in features:
        add("gmv_take_rate", "Take rate monetization for two-sided marketplaces.", 0.6)

    # Storage/bandwidth cost drivers suggest overage metrics
    cost_drivers = set(detected.get("cost_drivers") or [])
    if "storage" in cost_drivers:
        add("storage_gb", "Storage overage aligns with variable cost.", 0.7)
    if "bandwidth" in cost_drivers:
        add("bandwidth_gb", "Egress overage aligns with variable cost.", 0.6)

    # If nothing detected, fall back to common SaaS metrics
    if not candidates:
        add("seats", "Default for collaborative SaaS.", 0.5)
        add("usage_events", "Generic usage gates for feature access.", 0.4)

    # Deduplicate by metric keeping highest confidence
    best = {}
    for c in candidates:
        m = c["metric"]
        if m not in best or c["confidence"] > best[m]["confidence"]:
            best[m] = c
    return list(best.values())


def _compute_unit_prices(costs: Dict[str, float], margin_target: float) -> Dict[str, Any]:
    prices = {}
    for key in SUPPORTED_COST_KEYS:
        c = float(costs.get(key, DEFAULT_COGS.get(key, 0.0)))
        if c <= 0:
            continue
        # Price using target gross margin: price = cost / (1 - margin)
        p = c / max(0.05, (1.0 - float(margin_target)))
        prices[key] = round(p, 6)
    return prices


def _compute_price_hints(ctx: Context, unit_prices: Dict[str, float], margin_target: float) -> Dict[str, Any]:
    usage_dist = ctx.metrics.get("usage_distribution") or {}

    # Estimate per-seat baseline cost from p50 usage if available
    p50 = usage_dist.get("p50") or {}
    seat_usage = p50.get("per_seat") or {}

    variable_cost_per_seat = 0.0
    # Map usage keys to cost keys
    for k, qty in seat_usage.items():
        unit_key = {
            "api_calls": "api_call",
            "ai_tokens": "ai_token",
            "gpu_minutes": "gpu_minute",
            "storage_gb": "storage_gb_month"
        }.get(k)
        if unit_key and unit_key in unit_prices:
            # Convert price back to cost using margin if needed
            implied_cost = unit_prices[unit_key] * max(0.05, (1.0 - margin_target))
            variable_cost_per_seat += float(qty) * float(implied_cost)

    support_overhead = float(ctx.metrics.get("support_overhead_per_seat", 2.0))
    base_cost_per_seat = variable_cost_per_seat + support_overhead

    # Seat price hint: recover cost at target margin + value uplift factor based on collaboration/enterprise signals
    has_collab = "real_time_collaboration" in (ctx.detected.get("functionalities") or [])
    has_sso = "sso" in (ctx.detected.get("functionalities") or [])
    value_uplift = 1.15 + (0.15 if has_collab else 0.0) + (0.1 if has_sso else 0.0)

    seat_price = (base_cost_per_seat / max(0.05, (1.0 - margin_target))) * value_uplift if base_cost_per_seat > 0 else (15.0 if has_collab else 9.0)

    # Anchor to ARPU target if provided
    arpu_target = ctx.metrics.get("arpu_target")
    if arpu_target:
        # Assume 3 seats median for SMB
        implied_seat = float(arpu_target) / 3.0
        seat_price = (seat_price * 0.6) + (implied_seat * 0.4)

    seat_price_low = round(max(5.0, seat_price * 0.8), 2)
    seat_price_high = round(max(seat_price_low, seat_price * 1.2), 2)

    # Overage rates mirror unit prices with modest premium
    overage = {}
    for k, p in unit_prices.items():
        overage[k] = round(p * 1.15, 6)

    return {
        "per_seat_monthly_range": {"low": seat_price_low, "high": seat_price_high},
        "overage_unit_prices": overage
    }


def _build_plans(ctx: Context, features: set, value_metrics: List[Dict[str, Any]], unit_prices: Dict[str, float], price_hints: Dict[str, Any], currency: str) -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []

    # Determine baseline inclusions from FEATURE_RULES
    inclusions = {s["internal_key"]: set() for s in DEFAULT_PLAN_SHELLS}
    for f in features:
        rule = FEATURE_RULES.get(f)
        if not rule:
            continue
        plan_inc = rule.get("plan_inclusions", {})
        for plan_key, feats in plan_inc.items():
            if plan_key in inclusions:
                inclusions[plan_key].update(feats)

    # Determine quota defaults per plan based on DEFAULT_USAGE_BY_PLAN and features
    def plan_quota(plan_key: str) -> Dict[str, Any]:
        quota = {}
        base = DEFAULT_USAGE_BY_PLAN.get(plan_key, {})
        for k, v in base.items():
            quota[k] = v
        return quota

    per_seat_range = price_hints.get("per_seat_monthly_range", {"low": 9.0, "high": 19.0})

    # Free plan template
    free_plan = {
        "name": "Free",
        "price_hint": {"monthly": 0, "currency": currency},
        "packaging": {
            "seat_limit": 1 if ("real_time_collaboration" in features) else None,
            "workspace_limit": 1,
            "branding": "watermark",
            "support": "community"
        },
        "included_features": sorted(list(inclusions.get("free", set()))),
        "included_usage": plan_quota("free"),
        "overage": _overage_for_plan(unit_prices, multiplier=1.25, currency=currency)
    }
    plans.append(free_plan)

    # Pro plan template
    pro_seat = round(per_seat_range["low"], 2)
    pro_plan = {
        "name": "Pro",
        "price_hint": {"per_seat_monthly": pro_seat, "currency": currency},
        "packaging": {
            "seat_min": 1,
            "seat_max": 25,
            "workspace_limit": 3,
            "support": "email"
        },
        "included_features": sorted(list(inclusions.get("pro", set()))),
        "included_usage": plan_quota("pro"),
        "overage": _overage_for_plan(unit_prices, multiplier=1.15, currency=currency)
    }
    plans.append(pro_plan)

    # Business plan template
    biz_seat = round((per_seat_range["low"] + per_seat_range["high"]) / 2.0 * 1.4, 2)
    business_plan = {
        "name": "Business",
        "price_hint": {"per_seat_monthly": biz_seat, "currency": currency},
        "packaging": {
            "seat_min": 5,
            "seat_max": 500,
            "workspace_limit": None,
            "support": "priority",
            "security": ["saml_sso"] if "sso" in features else []
        },
        "included_features": sorted(list(inclusions.get("business", set()))),
        "included_usage": plan_quota("business"),
        "overage": _overage_for_plan(unit_prices, multiplier=1.1, currency=currency)
    }
    plans.append(business_plan)

    # Enterprise plan template
    ent_seat = round(max(biz_seat * 1.5, per_seat_range["high"] * 2.0), 2)
    enterprise_plan = {
        "name": "Enterprise",
        "price_hint": {"per_seat_monthly": ent_seat, "annual_contract_min": 20000, "currency": currency},
        "packaging": {
            "seat_min": 25,
            "support": "24x7_sla",
            "security": ["saml_sso", "scim", "audit_logs"],
            "contract": ["MSA", "DPA"],
            "deployment": ["multi_tenant", "private_cloud"]
        },
        "included_features": sorted(list(inclusions.get("enterprise", set()))),
        "included_usage": plan_quota("enterprise"),
        "overage": _overage_for_plan(unit_prices, multiplier=1.05, currency=currency)
    }
    if "on_prem" in features:
        enterprise_plan["packaging"]["deployment"].append("on_prem")
    plans.append(enterprise_plan)

    # Inject value metrics guidance per plan
    for p in plans:
        p["value_metrics_guidance"] = value_metrics

    return plans


def _overage_for_plan(unit_prices: Dict[str, float], multiplier: float, currency: str) -> Dict[str, Any]:
    over = {}
    for k, v in unit_prices.items():
        over[k] = {"price": round(v * multiplier, 6), "currency": currency}
    return over


def _build_add_ons(add_on_keys: List[str], unit_prices: Dict[str, float], currency: str) -> List[Dict[str, Any]]:
    add_ons = []
    for key in add_on_keys:
        lib = ADD_ON_LIBRARY.get(key)
        if not lib:
            continue
        addon = {"name": key, "description": lib.get("description"), "options": []}
        if key == "AI Pack":
            token_price = unit_prices.get("ai_token") or 0.0
            for b in lib.get("bundles", []):
                included = b.get("included_tokens", 0)
                list_price = included * token_price
                # Prepay discount
                discount = b.get("discount", 0.0)
                price = round(list_price * (1 - discount), 2)
                addon["options"].append({
                    "name": b.get("name"),
                    "included_tokens": included,
                    "price": price,
                    "currency": currency,
                    "effective_unit": round((price / max(1, included)), 6)
                })
        elif key == "White Label":
            addon["options"].append({"name": "White Label", "monthly": 499, "currency": currency})
        elif key == "Partner Program":
            addon["options"].append({"name": "Partner Silver", "monthly": 199, "currency": currency})
            addon["options"].append({"name": "Partner Gold", "monthly": 499, "currency": currency})
        add_ons.append(addon)
    return add_ons


def _propose_experiments(features: set, value_metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tests = []

    if any(vm["metric"] == "seats" for vm in value_metrics):
        tests.append({
            "name": "Seat cap on Free tier",
            "variants": [{"cap": 1}, {"cap": 3}],
            "goal": "Activation-to-conversion uplift",
            "duration_weeks": 4
        })

    if any(vm["metric"] in ("api_calls", "ai_tokens") for vm in value_metrics):
        tests.append({
            "name": "Overage price elasticity",
            "variants": [{"multiplier": 1.1}, {"multiplier": 1.3}],
            "goal": "Revenue without churn impact",
            "duration_weeks": 6
        })

    if "analytics_dashboard" in features:
        tests.append({
            "name": "Analytics Plus add-on uptake",
            "variants": [{"price": 19}, {"price": 29}],
            "goal": "Attach rate",
            "duration_weeks": 4
        })
    return tests


def _confidence(features: set, value_metrics: List[Dict[str, Any]], patterns: Dict[str, Any]) -> float:
    # Confidence increases with number of matched rules and clarity of value metrics
    matched_rules = sum(1 for f in features if f in FEATURE_RULES)
    vm_score = sum(vm.get("confidence", 0.5) for vm in value_metrics)
    pm_score = len(set(patterns.get("pricing_models", []))) * 0.5
    raw = 0.2 + clamp(matched_rules / 10.0, 0.0, 0.5) + clamp(vm_score / 5.0, 0.0, 0.3) + clamp(pm_score / 3.0, 0.0, 0.2)
    return clamp(raw, 0.1, 0.98)

