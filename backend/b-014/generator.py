import math
from datetime import datetime

DEFAULT_ALPHA = 0.05
DEFAULT_POWER = 0.80
Z_ALPHA_2 = 1.96  # two-tailed alpha=0.05
Z_BETA = 0.842    # power=0.80

DOMAIN_DEFAULTS = {
    "ecommerce": {
        "primary": ["conversion_rate"],
        "secondary": ["revenue_per_user", "average_order_value"],
        "guardrails": ["bounce_rate", "add_to_cart_rate", "latency_ms", "error_rate"]
    },
    "web": {
        "primary": ["ctr"],
        "secondary": ["dwell_time", "pages_per_session"],
        "guardrails": ["error_rate", "ttfb_ms", "cls", "lcp_ms"]
    },
    "mobile": {
        "primary": ["d1_retention"],
        "secondary": ["crash_free_sessions", "session_length"],
        "guardrails": ["app_start_time_ms", "battery_drain", "anr_rate"]
    },
    "healthcare": {
        "primary": ["auroc"],
        "secondary": ["sensitivity", "specificity"],
        "guardrails": ["privacy_risk", "fairness_gap", "calibration_error"]
    },
    "finance": {
        "primary": ["fraud_precision"],
        "secondary": ["fraud_recall", "aucpr"],
        "guardrails": ["risk_exposure", "false_positive_rate", "latency_ms"]
    },
    "marketing": {
        "primary": ["ctr"],
        "secondary": ["cvr", "cpa"],
        "guardrails": ["unsubscribe_rate", "spam_complaints", "frequency_cap_exceedance"]
    },
    "nlp": {
        "primary": ["accuracy"],
        "secondary": ["bleu", "rouge"],
        "guardrails": ["toxicity_rate", "bias_gap", "latency_ms"]
    },
    "vision": {
        "primary": ["top1_accuracy"],
        "secondary": ["map", "top5_accuracy"],
        "guardrails": ["latency_ms", "throughput_qps", "false_positive_rate"]
    },
    "ops": {
        "primary": ["latency_ms"],
        "secondary": ["error_rate", "throughput_qps"],
        "guardrails": ["cpu_utilization", "mem_usage", "cost_per_request"]
    }
}

DATASETS = {
    "ecommerce": [
        {"name": "UCI Online Retail", "url": "https://archive.ics.uci.edu/ml/datasets/online+retail"},
        {"name": "RetailRocket Recommender System Dataset", "url": "https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset"},
        {"name": "Instacart Market Basket Analysis", "url": "https://www.kaggle.com/competitions/instacart-market-basket-analysis"}
    ],
    "web": [
        {"name": "Criteo Display Advertising Challenge", "url": "https://www.kaggle.com/competitions/criteo-display-ad-challenge"},
        {"name": "Avazu CTR", "url": "https://www.kaggle.com/competitions/avazu-ctr-prediction"}
    ],
    "mobile": [
        {"name": "Google Play Store Apps", "url": "https://www.kaggle.com/datasets/lava18/google-play-store-apps"},
        {"name": "Mobile App A/B Testing Synthetic", "url": "https://www.kaggle.com/datasets/zhangluyuan/mobile-ab-testing"}
    ],
    "healthcare": [
        {"name": "UCI Heart Disease", "url": "https://archive.ics.uci.edu/ml/datasets/heart+Disease"},
        {"name": "MIMIC-III (restricted)", "url": "https://physionet.org/content/mimiciii/1.4/"}
    ],
    "finance": [
        {"name": "IEEE-CIS Fraud Detection", "url": "https://www.kaggle.com/competitions/ieee-fraud-detection"},
        {"name": "LendingClub Loan Data", "url": "https://www.kaggle.com/datasets/wordsforthewise/lending-club"}
    ],
    "marketing": [
        {"name": "Mailing Campaign (UCI Bank Marketing)", "url": "https://archive.ics.uci.edu/ml/datasets/bank+marketing"},
        {"name": "Online Shoppers Purchasing Intention", "url": "https://www.kaggle.com/datasets/roshansharma/online-shoppers-intention"}
    ],
    "nlp": [
        {"name": "IMDB Reviews", "url": "https://ai.stanford.edu/~amaas/data/sentiment/"},
        {"name": "SQuAD", "url": "https://rajpurkar.github.io/SQuAD-explorer/"},
        {"name": "GLUE", "url": "https://gluebenchmark.com/"}
    ],
    "vision": [
        {"name": "CIFAR-10", "url": "https://www.cs.toronto.edu/~kriz/cifar.html"},
        {"name": "COCO", "url": "https://cocodataset.org/"}
    ],
    "ops": [
        {"name": "Google Cluster Workload Traces", "url": "https://github.com/google/cluster-data"},
        {"name": "Azure Functions Dataset", "url": "https://github.com/Azure/AzurePublicDataset"}
    ],
    "general": [
        {"name": "UCI Machine Learning Repository", "url": "https://archive.ics.uci.edu/"},
        {"name": "Kaggle Datasets", "url": "https://www.kaggle.com/datasets"}
    ]
}

RISK_TEMPLATES = {
    "ecommerce": ["Novelty effects", "Bot traffic skew", "Revenue cannibalization", "Seasonality"],
    "web": ["SEO impact", "Page performance regressions", "Tracking pixel conflicts"],
    "mobile": ["App store rollout risks", "OS fragmentation", "Caching effects"],
    "healthcare": ["PHI exposure", "Model bias on subgroups", "Clinical safety"],
    "finance": ["Regulatory compliance", "Financial loss risk", "Model drift"],
    "marketing": ["List fatigue", "Sender reputation", "Attribution confounding"],
    "nlp": ["Toxic output", "Data leakage", "Hallucinations"],
    "vision": ["Domain shift", "Label noise", "Adversarial robustness"],
    "ops": ["Noisy neighbors", "Auto-scaling instability", "Cold start latency"]
}

INSTRUMENTATION_TEMPLATES = {
    "user": ["user_id", "treatment_group", "exposure_timestamp", "click", "convert", "revenue", "latency_ms", "error"],
    "session": ["session_id", "user_id", "treatment_group", "page_views", "clicks", "duration", "errors", "latency_ms"],
    "item": ["item_id", "user_id", "treatment_group", "impressions", "clicks", "purchases"]
}


def _parse_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(',') if v.strip()]


def _clamp01(x):
    return max(0.0, min(1.0, float(x)))


def estimate_sample_size_proportions(p1, mde, alpha=DEFAULT_ALPHA, power=DEFAULT_POWER):
    try:
        p1 = _clamp01(p1)
        p2 = _clamp01(p1 + mde)
        if p1 == p2:
            return None
        # Using normal approximation for two-sample proportions, equal n per group
        p_bar = (p1 + p2) / 2.0
        q1 = 1 - p1
        q2 = 1 - p2
        term1 = Z_ALPHA_2 * math.sqrt(2 * p_bar * (1 - p_bar))
        term2 = Z_BETA * math.sqrt(p1 * q1 + p2 * q2)
        n = ((term1 + term2) ** 2) / ((p2 - p1) ** 2)
        return int(math.ceil(n))
    except Exception:
        return None


def choose_design(num_iv, unit_of_randomization, constraints_text):
    constraints_text = (constraints_text or "").lower()
    if num_iv and num_iv > 1:
        return {
            "type": "factorial_between_subjects",
            "arms": 2 ** num_iv,
            "notes": "Full-factorial design across independent variables"
        }
    # Default A/B between subjects
    design = {
        "type": "ab_between_subjects",
        "arms": 2,
        "notes": "Standard A/B test with parallel groups"
    }
    # Consider within-subject if low carryover risks
    if unit_of_randomization == "user" and not any(k in constraints_text for k in ["carryover", "learning", "memory", "contamination"]):
        design["alternate"] = {
            "type": "within_subjects_switchback",
            "notes": "Consider switchback/within-subject if contamination risk is low"
        }
    return design


def suggest_metrics(domain, dependent_metrics):
    domain_key = (domain or "").lower().strip()
    defaults = DOMAIN_DEFAULTS.get(domain_key, DOMAIN_DEFAULTS.get("web"))
    dep = _parse_list(dependent_metrics)
    primary = dep[0] if dep else (defaults["primary"][0] if defaults["primary"] else "primary_metric")
    secondary = dep[1:] if len(dep) > 1 else defaults.get("secondary", [])
    guardrails = list(defaults.get("guardrails", []))
    return {
        "primary": primary,
        "secondary": secondary,
        "guardrails": guardrails
    }


def suggest_datasets(domain):
    domain_key = (domain or "").lower().strip()
    ds = DATASETS.get(domain_key, []) + DATASETS.get("general", [])
    # Deduplicate by name
    seen = set()
    out = []
    for d in ds:
        if d["name"] not in seen:
            out.append(d)
            seen.add(d["name"])
    return out


def build_hypotheses(iv_list, metrics):
    iv_desc = ", ".join(iv_list) if iv_list else "the treatment"
    hypotheses = []
    all_metrics = [metrics.get("primary")] + list(metrics.get("secondary", []))
    for m in [x for x in all_metrics if x]:
        h0 = f"H0: {iv_desc} has no effect on {m}."
        h1 = f"H1: {iv_desc} changes {m} by at least the minimum detectable effect."
        hypotheses.append({"metric": m, "null": h0, "alternative": h1})
    return hypotheses


def estimate_duration_days(sample_size_per_group, arms, traffic_per_day):
    try:
        total_needed = sample_size_per_group * arms
        if not traffic_per_day or traffic_per_day <= 0:
            return None
        days = total_needed / float(traffic_per_day)
        return round(days, 2)
    except Exception:
        return None


def analysis_plan(metrics):
    primary = metrics.get("primary")
    secondary = metrics.get("secondary", [])
    tests = []
    for m in [primary] + list(secondary):
        if m is None:
            continue
        m_low = m.lower()
        if any(k in m_low for k in ["rate", "ctr", "cvr", "conversion", "retention", "error"]):
            tests.append({"metric": m, "test": "two-proportion z-test", "tails": "two", "alpha": DEFAULT_ALPHA})
        elif any(k in m_low for k in ["revenue", "value", "time", "latency", "duration", "dwell", "length"]):
            tests.append({"metric": m, "test": "two-sample t-test (Welch)", "tails": "two", "alpha": DEFAULT_ALPHA})
        else:
            tests.append({"metric": m, "test": "nonparametric (Mann-Whitney U) or appropriate", "tails": "two", "alpha": DEFAULT_ALPHA})
    return {
        "tests": tests,
        "multiple_testing": "Control FDR (Benjamini-Hochberg) across secondary metrics",
        "effect_size_reporting": "Report absolute and relative lift with 95% CI",
        "stopping_rule": "Fixed horizon unless sequential methods are explicitly planned"
    }


def ethics_and_compliance(domain):
    domain_key = (domain or "").lower().strip()
    notes = []
    if domain_key in ["healthcare", "finance"]:
        notes.append("Obtain necessary IRB/compliance approvals before data collection")
        notes.append("Minimize collection of sensitive attributes; apply privacy-by-design")
    notes.append("Ensure consent and transparent user communication where applicable")
    notes.append("Assess fairness across key cohorts and mitigate disparities")
    return notes


def rollout_plan():
    return {
        "strategy": "Gradual rollout: 1% -> 10% -> 50% -> 100% with monitoring gates",
        "holdout": "Maintain a small long-lived holdout (1-5%) for baselining",
        "kill_switch": "Ability to instantly disable treatment on guardrail breach"
    }


def generate_experiment_design(payload: dict) -> dict:
    title = (payload.get("title") or "Experiment").strip()
    domain = (payload.get("domain") or "web").strip()
    research_question = (payload.get("research_question") or "").strip()
    iv = _parse_list(payload.get("independent_variables"))
    dv = _parse_list(payload.get("dependent_metrics"))
    unit = (payload.get("unit_of_randomization") or "user").strip().lower()
    constraints = (payload.get("constraints") or "").strip()

    baseline_rate = payload.get("baseline_rate")
    mde = payload.get("mde")
    traffic_per_day = payload.get("traffic_per_day")

    try:
        baseline_rate = float(baseline_rate) if baseline_rate is not None and str(baseline_rate) != "" else None
    except Exception:
        baseline_rate = None
    try:
        mde = float(mde) if mde is not None and str(mde) != "" else None
    except Exception:
        mde = None
    try:
        traffic_per_day = int(traffic_per_day) if traffic_per_day is not None and str(traffic_per_day) != "" else None
    except Exception:
        traffic_per_day = None

    design = choose_design(len(iv), unit, constraints)
    metrics = suggest_metrics(domain, dv)

    sample_size = None
    duration_days = None
    if baseline_rate is not None and mde is not None:
        n_per_group = estimate_sample_size_proportions(baseline_rate, mde)
        if n_per_group:
            arms = design.get("arms", 2)
            duration_days = estimate_duration_days(n_per_group, arms, traffic_per_day) if traffic_per_day else None
            sample_size = {
                "per_group": n_per_group,
                "total": n_per_group * arms,
                "assumptions": {
                    "alpha": DEFAULT_ALPHA,
                    "power": DEFAULT_POWER,
                    "baseline_rate": baseline_rate,
                    "mde_abs": mde,
                    "test": "two-proportion z-test (normal approximation)",
                    "equal_allocation": True
                }
            }

    datasets = suggest_datasets(domain)
    hypotheses = build_hypotheses(iv, metrics)
    risks = RISK_TEMPLATES.get((domain or "").lower().strip(), [])
    instrumentation = INSTRUMENTATION_TEMPLATES.get(unit, INSTRUMENTATION_TEMPLATES["user"]) + ["experiment_version", "client_type", "cohort"]

    result = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "title": title,
        "domain": domain,
        "research_question": research_question,
        "unit_of_randomization": unit,
        "independent_variables": iv,
        "metrics": metrics,
        "design": design,
        "hypotheses": hypotheses,
        "datasets": datasets,
        "sample_size": sample_size,
        "estimated_duration_days": duration_days,
        "randomization": {
            "allocation": "Equal split across arms",
            "stratification": "Optional: stratify by key covariates (e.g., geography, device)",
            "exclusions": "Exclude employees, test accounts, obvious bots"
        },
        "analysis_plan": analysis_plan(metrics),
        "instrumentation": instrumentation,
        "constraints": constraints,
        "risks": risks,
        "ethics": ethics_and_compliance(domain),
        "rollout_plan": rollout_plan(),
        "monitoring": {
            "realtime_dashboards": ["primary metric", "guardrails", "traffic split"],
            "anomaly_alerts": ["error_rate spike", "latency regression", "metric drops>3σ"],
            "data_quality": ["missing events", "id collisions", "timestamp skew"]
        },
        "decision_criteria": {
            "primary": "Statistically significant improvement on primary metric without guardrail violations",
            "secondary": "No material regressions on secondary metrics",
            "practical_significance": "Lift exceeds pre-defined MDE and is operationally acceptable"
        }
    }

    return result

