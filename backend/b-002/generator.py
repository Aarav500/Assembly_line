import re
import math
import hashlib
from datetime import datetime

INDUSTRY_KEYWORDS = {
    "ai": "AI/ML",
    "assistant": "AI/ML",
    "chat": "AI/ML",
    "genai": "AI/ML",
    "gpt": "AI/ML",
    "marketplace": "Marketplace",
    "analytics": "Analytics",
    "dashboard": "Analytics",
    "insights": "Analytics",
    "no-code": "Dev Tools",
    "low-code": "Dev Tools",
    "builder": "Dev Tools",
    "jobs": "HR/Recruiting",
    "hiring": "HR/Recruiting",
    "recruit": "HR/Recruiting",
    "health": "Health",
    "fitness": "Health",
    "wellness": "Health",
    "education": "EdTech",
    "learn": "EdTech",
    "study": "EdTech",
    "finance": "FinTech",
    "budget": "FinTech",
    "invoice": "FinTech",
    "supply": "Logistics",
    "logistics": "Logistics",
    "shipping": "Logistics",
    "ecommerce": "E-commerce",
    "store": "E-commerce",
    "shop": "E-commerce",
    "creator": "Creator Economy",
    "content": "Creator Economy",
    "crm": "SaaS",
    "sales": "SaaS",
    "marketing": "SaaS",
}

AUDIENCE_HINTS = {
    "founder": "Founders",
    "startup": "Founders",
    "developer": "Developers",
    "engineer": "Developers",
    "marketer": "Marketers",
    "sales": "Sales Teams",
    "teacher": "Educators",
    "student": "Students",
    "designer": "Designers",
    "freelancer": "Freelancers",
    "creator": "Creators",
    "consumer": "Consumers",
    "team": "Teams",
    "enterprise": "Enterprise",
    "smb": "SMBs",
    "small business": "SMBs",
    "shopify": "E-commerce Teams",
    "shop owner": "E-commerce Teams",
}

VERB_TO_VALUE = {
    "automate": "save time and reduce manual effort",
    "optimize": "improve performance and efficiency",
    "discover": "find relevant options faster",
    "learn": "accelerate learning with guidance",
    "track": "gain visibility and control",
    "manage": "organize processes and reduce chaos",
    "create": "produce higher-quality output faster",
    "monetize": "increase revenue and LTV",
    "sell": "boost conversion and sales",
    "hire": "reduce time-to-hire and improve quality",
    "analyze": "turn data into actionable insights",
    "collaborate": "work together seamlessly",
    "plan": "reduce uncertainty and align teams",
}

NAME_CANDIDATES = [
    "IdeaExpandr", "MVP Forge", "ScopeSprint", "ProblemSolver Pro", "VentureCraft",
    "LaunchStencil", "MVPCanvas", "OneLine Labs", "SparkToScope", "IdeaAmp",
    "ScopeSmith", "PitchPilot", "SolutionWeaver", "RapidSpec", "Blueprintr"
]

PRICING_TIERS = {
    "Consumers": [
        {"tier": "Free", "price": "$0", "includes": ["Basic generation", "Limited saves"]},
        {"tier": "Plus", "price": "$9/mo", "includes": ["Unlimited runs", "Export to PDF/Markdown", "Custom tones"]},
        {"tier": "Pro", "price": "$19/mo", "includes": ["Team sharing", "Templates", "Priority support"]},
    ],
    "SMBs": [
        {"tier": "Starter", "price": "$29/mo", "includes": ["3 seats", "Unlimited projects", "Exports"]},
        {"tier": "Growth", "price": "$79/mo", "includes": ["10 seats", "Advanced templates", "Integrations"]},
        {"tier": "Business", "price": "$199/mo", "includes": ["25 seats", "SAML/SSO", "Admin & reporting"]},
    ],
    "Enterprise": [
        {"tier": "Custom", "price": "Contact sales", "includes": ["Unlimited seats", "Security review", "SLAs & support"]}
    ],
    "Developers": [
        {"tier": "Free", "price": "$0", "includes": ["100 API calls/mo", "Community support"]},
        {"tier": "Builder", "price": "$49/mo", "includes": ["5k API calls/mo", "Rate limit bumps", "Logs"]},
        {"tier": "Scale", "price": "$199/mo", "includes": ["50k API calls/mo", "Priority support", "Webhooks"]},
    ],
    "Founders": [
        {"tier": "Free", "price": "$0", "includes": ["Core canvas", "1 export/day"]},
        {"tier": "Pro", "price": "$15/mo", "includes": ["Unlimited exports", "Custom sections", "Collaboration"]},
        {"tier": "Team", "price": "$59/mo", "includes": ["5 seats", "Shared templates", "Comments"]},
    ],
}


def stable_index(text: str, modulo: int) -> int:
    h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
    return h % modulo


def guess_industry(one_liner: str) -> str:
    l = one_liner.lower()
    for k, v in INDUSTRY_KEYWORDS.items():
        if k in l:
            return v
    return "SaaS"


def guess_audience(one_liner: str) -> str:
    l = one_liner.lower()
    for k, v in AUDIENCE_HINTS.items():
        if k in l:
            return v
    # Heuristic: if mentions team/enterprise or b2b-like verbs
    if any(w in l for w in ["team", "workflow", "pipeline", "crm", "ops", "operations", "sales", "marketing", "enterprise"]):
        return "SMBs"
    return "Consumers"


def extract_actions(one_liner: str):
    l = one_liner.lower()
    verbs = []
    for v in VERB_TO_VALUE.keys():
        if v in l:
            verbs.append(v)
    if not verbs:
        # simple regex to extract first verb-ish word after "to"
        m = re.search(r"to\s+([a-z\-]+)", l)
        if m:
            verbs.append(m.group(1))
    return list(dict.fromkeys(verbs))  # unique preserve order


def extract_target(one_liner: str):
    l = one_liner.lower()
    # try "for X" phrase
    m = re.search(r"for\s+([a-z0-9\-\s]+)$", l)
    if m:
        return m.group(1).strip().strip('.')
    # try within the line "for X to Y"
    m = re.search(r"for\s+([a-z0-9\-\s]+?)\s+(to|that|who)\s", l)
    if m:
        return m.group(1).strip()
    # fallback from audience guess
    return guess_audience(one_liner)


def make_name(one_liner: str) -> str:
    idx = stable_index(one_liner, len(NAME_CANDIDATES))
    return NAME_CANDIDATES[idx]


def make_tagline(name: str, one_liner: str, industry: str):
    core = one_liner.strip().rstrip('.')
    return f"{name}: {core}"


def tone_filter(text: str, tone: str):
    if tone == "concise":
        # remove extra adjectives and keep sentences short
        text = re.sub(r",?\s*(highly|incredibly|significantly|world[- ]class|best[- ]in[- ]class|robust|cutting[- ]edge)\s+", " ", text, flags=re.I)
    elif tone == "pitchy":
        # add mild excitement
        if not text.endswith("!") and len(text) < 120:
            text += "!"
    return text


def build_problem(one_liner: str, audience: str, actions, industry: str, tone: str):
    action_phrase = actions[0] if actions else "get results"
    problem_summary = f"{audience} struggle to {action_phrase} reliably using current alternatives. Solutions today are fragmented, manual, or too complex, leading to wasted time and inconsistent outcomes."
    problem_summary = tone_filter(problem_summary, tone)
    details = [
        f"Time cost: hours lost each week attempting to {action_phrase} across tools.",
        "Quality risk: inconsistent output and lack of standardization.",
        "Visibility gap: hard to measure what works and iterate quickly.",
    ]
    why_now = [
        f"Shift to {industry} and automation is raising expectations for speed and quality.",
        "Cheap enabling tech (APIs, cloud, integrations) makes a lighter solution viable now.",
        "Budget pressure increases demand for measurable ROI within weeks, not months.",
    ]
    evidence_hyp = [
        "Users hack together spreadsheets and templates to compensate.",
        "High intent search terms suggest strong demand for simpler workflows.",
        "Communities ask for practical, step-by-step playbooks versus generic advice.",
    ]
    return {
        "summary": problem_summary,
        "who": audience,
        "details": details,
        "why_now": why_now,
        "evidence_hypotheses": evidence_hyp,
    }


def feature_suggestions(industry: str, actions, audience: str):
    base = [
        "Guided canvas to structure problem and solution",
        "Templates tuned to use case and audience",
        "Export to PDF, Markdown, and slides",
        "Versioning and comparison across iterations",
    ]
    ai = [
        "AI expansion from one-liners into detailed sections",
        "Auto-generate KPIs with formulas and targets",
        "Smart monetization suggestions based on audience",
    ]
    collab = [
        "Shareable links and team comments",
        "Role-based access (viewer/editor)",
    ]
    analytics = [
        "Progress checklist and readiness score",
        "Benchmark library of example KPIs by industry",
    ]
    picks = base + collab + analytics
    if industry in ("AI/ML", "SaaS", "Analytics", "Dev Tools"):
        picks = ai + picks
    # Prioritize action-aligned features
    if actions:
        if any(a in actions for a in ["automate", "optimize", "analyze"]):
            picks.insert(0, "Automated gap analysis and suggestions")
        if any(a in actions for a in ["create", "generate"]):
            picks.insert(0, "One-click draft generation for each section")
    return list(dict.fromkeys(picks))


def build_solution(name: str, industry: str, audience: str, actions, tone: str):
    positioning = f"{name} turns a single sentence into a structured plan: problem, solution, KPIs, and monetization in minutes—so {audience.lower()} can move from idea to MVP fast."
    positioning = tone_filter(positioning, tone)
    features = feature_suggestions(industry, actions, audience)
    journey = [
        "Enter one-liner",
        "Select audience and tone",
        "Get structured plan with editable sections",
        "Export and share with stakeholders",
        "Iterate with templates and checklists",
    ]
    mvp_scope = {
        "must": [
            "One-liner parser and context extraction",
            "Generate problem, solution, KPIs, monetization",
            "Editable UI and export to Markdown/PDF",
        ],
        "should": [
            "Template presets by industry",
            "Collaboration (share link, comments)",
        ],
        "could": [
            "API access",
            "Benchmark library and examples",
        ],
    }
    return {
        "positioning": positioning,
        "key_features": features,
        "user_journey": journey,
        "mvp_scope": mvp_scope,
    }


def kpi_catalog(industry: str, audience: str):
    # A compact, broadly applicable KPI set with categories
    kpis = [
        {"category": "acquisition", "name": "Signup Conversion Rate", "definition": "Percent of visitors who sign up", "formula": "signups / unique_visitors", "target_90d": ">= 5%"},
        {"category": "activation", "name": "Activation Rate (AHA)", "definition": "Percent of signups who complete first plan export", "formula": "activated_users / signups", "target_90d": ">= 40%"},
        {"category": "retention", "name": "D7 Retention", "definition": "Users active 7 days after signup", "formula": "active_day7 / signups", "target_90d": ">= 20%"},
        {"category": "retention", "name": "WAU/MAU", "definition": "Stickiness ratio", "formula": "weekly_active_users / monthly_active_users", "target_90d": ">= 0.45"},
        {"category": "engagement", "name": "Plans Created per User", "definition": "Median plans per active user per month", "formula": "plans_created / MAU", "target_90d": ">= 2"},
        {"category": "quality", "name": "Edit Acceptance Rate", "definition": "Percent of AI-generated sections kept with minimal edits", "formula": "sections_kept / sections_generated", "target_90d": ">= 60%"},
        {"category": "performance", "name": "Time to First Plan", "definition": "Median minutes from one-liner to export", "formula": "median(minutes_to_export)", "target_90d": "<= 5 min"},
        {"category": "revenue", "name": "Free->Paid Conversion", "definition": "Percent of free users who upgrade within 30 days", "formula": "new_payers_30d / new_free_30d", "target_90d": ">= 3%"},
        {"category": "revenue", "name": "ARPU", "definition": "Average revenue per paying user per month", "formula": "MRR / paying_users", "target_90d": "$12+"},
        {"category": "growth", "name": "Organic Signup Share", "definition": "Percent of signups from organic channels", "formula": "organic_signups / total_signups", "target_90d": ">= 40%"},
        {"category": "efficiency", "name": "CAC Payback", "definition": "Months to recoup acquisition cost", "formula": "CAC / (ARPU * gross_margin)", "target_90d": "<= 6 mo"},
        {"category": "satisfaction", "name": "NPS", "definition": "Net Promoter Score from in-app survey", "formula": "promoters% - detractors%", "target_90d": ">= 30"},
    ]
    if industry in ("AI/ML", "Analytics"):
        kpis.insert(6, {"category": "performance", "name": "Generation Latency", "definition": "Median seconds to generate plan", "formula": "p50(seconds_per_generation)", "target_90d": "<= 3s"})
        kpis.insert(6, {"category": "quality", "name": "Factual Corrections per Plan", "definition": "Edits flagged as factual corrections", "formula": "corrections / plans_exported", "target_90d": "<= 0.3"})
    return kpis


def monetization_models(audience: str, industry: str):
    rec = []
    alt = []

    if audience in ("SMBs", "Developers", "Founders", "Teams"):
        rec.append({
            "model": "Freemium + Subscription",
            "why": "Low-friction adoption, upgrade for collaboration and exports",
            "tiers": PRICING_TIERS.get(audience, PRICING_TIERS["SMBs"]),
            "pros": ["Viral loops via shared links", "Predictable MRR"],
            "cons": ["Free support load", "Optimize for activation to convert"],
        })
        rec.append({
            "model": "Usage-based (API or credits)",
            "why": "Align price with value when generation volume varies",
            "tiers": [
                {"tier": "Pay-as-you-go", "price": "$0.50 per plan", "includes": ["No monthly minimum"]},
                {"tier": "Committed", "price": "$99+/mo", "includes": ["Discounted rates", "SLA"]},
            ],
            "pros": ["Scales with heavy users", "Good for dev integrations"],
            "cons": ["Revenue volatility", "Requires rate limiting"],
        })
    else:
        rec.append({
            "model": "Subscription (Consumer)",
            "why": "Simple pricing with clear value threshold",
            "tiers": PRICING_TIERS.get("Consumers"),
            "pros": ["Low cognitive load", "Churn controllable via engagement"],
            "cons": ["Lower ARPU", "Requires strong retention"],
        })
        alt.append({
            "model": "One-time Template Packs",
            "why": "Monetize premium content bundles",
            "pricing": "$19-$49 per pack",
            "pros": ["Non-recurring revenue boost", "Great for affiliates"],
            "cons": ["Less predictable", "Inventory upkeep"],
        })

    alt.append({
        "model": "Team Licenses",
        "why": "Capture value in collaborative planning",
        "pricing": "$10-$20 per seat/mo",
        "pros": ["Higher ARPU", "Land and expand"],
        "cons": ["Procurement friction", "Requires admin features"],
    })

    return {"recommended": rec, "alternatives": alt}


def go_to_market(audience: str, industry: str):
    channels = [
        "Product Hunt launch with clear before/after visuals",
        "Twitter/LinkedIn threads showcasing transformations from one-line to plan",
        "Templates library SEO (e.g., 'AI startup KPI template')",
        "Founder communities and newsletters",
        "Lightweight YouTube walkthroughs and shorts",
    ]
    if audience in ("Developers", "SMBs"):
        channels.insert(0, "Embed on dev tool directories and startup lists")
        channels.append("Zapier/Make templates for workflows")
    if industry in ("AI/ML",):
        channels.append("Open-source a basic template to drive backlinks")
    launch_plan = [
        "Week 1: 5 templates + waitlist + teaser demos",
        "Week 2: Private beta with feedback form and fast iterations",
        "Week 3: PH launch + partner posts + customer stories",
        "Week 4: Double down on converting top channels, add pricing",
    ]
    return {"channels": channels, "launch_plan": launch_plan}


def assumptions(one_liner: str, audience: str):
    return [
        f"{audience} will provide a clear one-liner that maps to standard planning sections.",
        "Users prefer speed and structure over total customization initially.",
        "Export and sharing are primary triggers for perceived value.",
        "Templates per industry increase activation and retention.",
    ]


def risks_and_mitigations():
    return [
        {"risk": "Generic outputs reduce perceived quality", "mitigation": "Collect edits to learn, add industry presets, examples"},
        {"risk": "Low conversion from free to paid", "mitigation": "Gate exports/templates, add collaboration as paid"},
        {"risk": "Competition from general LLM products", "mitigation": "Own the opinionated workflow and benchmarks"},
        {"risk": "Churn after first success", "mitigation": "Add iteration loops, roadmap, scoring, and templates"},
    ]


def timeline():
    return [
        {"week": 1, "milestone": "MVP skeleton: input form, generator, JSON API"},
        {"week": 2, "milestone": "Templates by industry, exports, basic auth"},
        {"week": 3, "milestone": "Sharing, comments, launch assets"},
        {"week": 4, "milestone": "Public launch + pricing + analytics"},
    ]


def parse_core(one_liner: str):
    l = one_liner.strip()
    audience = guess_audience(l)
    industry = guess_industry(l)
    actions = extract_actions(l)
    target_phrase = extract_target(l)
    return audience, industry, actions, target_phrase


def generate_plan(one_liner: str, tone: str = "professional"):
    name = make_name(one_liner)
    audience, industry, actions, target_phrase = parse_core(one_liner)
    tagline = make_tagline(name, one_liner, industry)

    problem = build_problem(one_liner, audience, actions, industry, tone)
    solution = build_solution(name, industry, audience, actions, tone)
    kpis = kpi_catalog(industry, audience)
    monetization = monetization_models(audience, industry)
    gtm = go_to_market(audience, industry)

    elevator = f"{name} expands a single sentence into a compelling plan—problem, solution, KPIs, and monetization—so {audience.lower()} can validate and launch faster."
    elevator = tone_filter(elevator, tone)

    plan = {
        "meta": {
            "name": name,
            "slug": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
            "industry": industry,
            "audience": audience,
            "tone": tone,
        },
        "pitch": {
            "tagline": tagline,
            "one_sentence": tone_filter(one_liner.strip(), tone),
            "elevator_pitch": elevator,
        },
        "problem": problem,
        "solution": solution,
        "kpis": kpis,
        "monetization": monetization,
        "go_to_market": gtm,
        "assumptions": assumptions(one_liner, audience),
        "risks": risks_and_mitigations(),
        "next_steps": timeline(),
    }

    return plan

