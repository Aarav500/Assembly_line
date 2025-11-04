from .utils import make_rng, uid, pick, pick_n, pick_weighted, clamp

FIRST_NAMES = {
    "neutral": [
        "Alex", "Taylor", "Jordan", "Casey", "Riley", "Avery", "Morgan", "Jamie", "Rowan", "Cameron",
        "Drew", "Skyler", "Parker", "Quinn", "Reese"
    ],
    "female": [
        "Sophia", "Emma", "Olivia", "Ava", "Mia", "Isabella", "Amelia", "Harper", "Evelyn", "Abigail"
    ],
    "male": [
        "Liam", "Noah", "Oliver", "Elijah", "James", "William", "Benjamin", "Lucas", "Henry", "Alexander"
    ]
}

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
]

LOCATIONS = [
    "New York, USA", "San Francisco, USA", "Austin, USA", "Toronto, Canada", "Vancouver, Canada",
    "London, UK", "Manchester, UK", "Berlin, Germany", "Munich, Germany", "Stockholm, Sweden",
    "Sydney, Australia", "Melbourne, Australia", "Singapore", "Bengaluru, India", "Delhi, India",
    "Sao Paulo, Brazil", "Mexico City, Mexico", "Paris, France", "Amsterdam, Netherlands", "Barcelona, Spain"
]

EDUCATION = [
    "High school diploma", "Some college", "Associate degree", "Bachelor's degree", "Master's degree",
    "Professional certification", "Doctorate"
]

FAMILY_STATUS = [
    "Single", "Married", "Married with young children", "Married with teens", "Living with partner",
    "Single parent", "Empty nester"
]

PRONOUNS = [
    "she/her", "he/him", "they/them"
]

EMPLOYMENT = [
    "Full-time", "Part-time", "Freelancer", "Self-employed", "Unemployed", "Student", "Retired"
]

TECH_PROFICIENCY = [
    ("Novice", 1), ("Basic", 2), ("Comfortable", 3), ("Advanced", 4), ("Power user", 5)
]

ACCESSIBILITY_NEEDS = [
    "None", "Color vision deficiency", "Dyslexia", "Screen reader user", "Motor impairment",
    "Hearing impairment", "Photosensitivity"
]

DEVICES = [
    "iPhone", "Android phone", "iPad", "Android tablet", "Windows laptop", "MacBook", "Linux desktop",
    "Chromebook"
]

CHANNELS = ["Email", "SMS", "In-app", "Push notification", "Social media", "Phone support", "Live chat"]

ARCHETYPES = [
    "Busy Multitasker", "Budget-Conscious Planner", "Early Adopter", "Skeptical Evaluator",
    "Accessibility Advocate", "Privacy-Conscious", "Data-Driven Optimizer", "Community-Oriented Collaborator"
]

VALUES = [
    "Convenience", "Reliability", "Transparency", "Security", "Simplicity", "Speed", "Affordability",
    "Personalization", "Sustainability"
]

MOTIVATIONS = [
    "Save time", "Save money", "Reduce stress", "Gain control", "Learn new skills", "Grow business",
    "Stay organized", "Be more productive"
]

FRUSTRATIONS = [
    "Hidden fees", "Complicated setup", "Slow performance", "Poor customer support", "Bugs and crashes",
    "Confusing UI", "Lack of integrations", "Limited mobile features"
]

INDUSTRY_TITLES = {
    "Fintech": ["Freelance Accountant", "Bookkeeper", "Finance Manager", "Small Business Owner", "Trader"],
    "E-commerce": ["Store Owner", "Merchandiser", "Operations Manager", "Customer Support Lead"],
    "Healthcare": ["Nurse", "Clinic Manager", "Care Coordinator", "Medical Biller"],
    "Education": ["Teacher", "Instructional Designer", "Program Coordinator", "Student"],
    "SaaS": ["Product Manager", "Customer Success Manager", "Developer", "Sales Ops"],
    "General": ["Project Manager", "Marketing Specialist", "Analyst", "Consultant", "Student", "Freelancer"]
}

COMPETITORS = {
    "Fintech": ["QuickBooks", "Wave", "FreshBooks", "Xero", "Stripe"],
    "E-commerce": ["Shopify", "Wix", "Squarespace", "BigCommerce"],
    "Healthcare": ["Epic", "Cerner", "Kareo"],
    "Education": ["Google Classroom", "Canvas", "Moodle"],
    "SaaS": ["Notion", "Asana", "Trello", "Monday"],
    "General": ["Google Sheets", "Excel", "Email", "Paper"]
}


def _age_for_audience(rng, audience):
    if not audience:
        return rng.randint(22, 58)
    aud = " ".join(audience).lower()
    if any(x in aud for x in ["student", "junior", "early-career", "graduate"]):
        return rng.randint(18, 27)
    if any(x in aud for x in ["retiree", "senior", "elder"]):
        return rng.randint(60, 76)
    if any(x in aud for x in ["freelancer", "startup", "small business"]):
        return rng.randint(24, 46)
    return rng.randint(22, 58)


def _income_range(rng, industry):
    buckets = [
        ("< $35k", 0.15),
        ("$35k–$60k", 0.3),
        ("$60k–$90k", 0.25),
        ("$90k–$130k", 0.2),
        ("> $130k", 0.1)
    ]
    # Slight shift for some industries
    if industry.lower() in ["fintech", "saas"]:
        buckets = [
            ("< $35k", 0.1),
            ("$35k–$60k", 0.25),
            ("$60k–$90k", 0.3),
            ("$90k–$130k", 0.25),
            ("> $130k", 0.1)
        ]
    # Convert to weights out of 100
    choices = [(label, int(w * 100)) for label, w in buckets]
    return pick_weighted(rng, choices)


def _tech_proficiency(rng, audience):
    weights = [("Novice", 10), ("Basic", 20), ("Comfortable", 35), ("Advanced", 25), ("Power user", 10)]
    aud = " ".join(audience).lower()
    if any(x in aud for x in ["developer", "engineer", "designer", "tech", "startup"]):
        weights = [("Novice", 5), ("Basic", 15), ("Comfortable", 30), ("Advanced", 30), ("Power user", 20)]
    label = pick_weighted(rng, weights)
    level = next((lvl for lbl, lvl in [(l, i+1) for i, (l, _) in enumerate(TECH_PROFICIENCY)] if lbl == label), 3)
    return {"label": label, "level": level}


def _devices(rng):
    primary = pick_weighted(rng, [("iPhone", 25), ("Android phone", 35), ("Windows laptop", 22), ("MacBook", 18)])
    others = [d for d in DEVICES if d != primary]
    extra = rng.sample(others, rng.randint(1, 3))
    devices = [primary] + extra
    return [{"device": d, "usage_frequency": pick_weighted(rng, [("Daily", 60), ("Weekly", 30), ("Monthly", 10)])} for d in devices]


def _accessibility_needs(rng):
    if rng.random() < 0.78:
        return []
    needs = [n for n in ACCESSIBILITY_NEEDS if n != "None"]
    return rng.sample(needs, rng.randint(1, min(2, len(needs))))


def _personality(rng):
    # Big Five-like, 1-5
    return {
        "openness": rng.randint(2, 5),
        "conscientiousness": rng.randint(2, 5),
        "extraversion": rng.randint(1, 5),
        "agreeableness": rng.randint(2, 5),
        "neuroticism": rng.randint(1, 4)
    }


def _goals(rng, product, industry):
    base = [
        f"Use {product} without a steep learning curve",
        "Avoid manual work by automating routine tasks",
        "Keep data safe and private",
        "Get quick insight to make decisions"
    ]
    if industry.lower() == "fintech":
        base += ["Track income/expenses reliably", "Send invoices faster", "Simplify taxes"]
    if industry.lower() == "e-commerce":
        base += ["Increase conversion rates", "Manage inventory efficiently"]
    return rng.sample(base, min(3, len(base)))


def _frustrations(rng, industry):
    base = FRUSTRATIONS.copy()
    if industry.lower() == "fintech":
        base += ["Bank connection failures", "Delayed payouts"]
    return rng.sample(base, 3)


def _behaviors(rng, audience):
    choices = [
        "Reads reviews before trying new tools",
        "Prefers mobile over desktop for quick tasks",
        "Batch processes work during evenings",
        "Experiments with new features then adopts selectively",
        "Relies on templates to save time",
        "Shares feedback with support when blocked"
    ]
    return rng.sample(choices, 3)


def _quote(rng, product):
    patterns = [
        f"I just want {product} to get out of my way so I can focus on work.",
        f"If {product} can save me 10 minutes a day, I'm in.",
        f"Don't make me read a manual to use {product}.",
        f"I need {product} to be reliable, even on bad Wi‑Fi."
    ]
    return pick(rng, patterns)


def _role_title(rng, industry):
    titles = INDUSTRY_TITLES.get(industry, INDUSTRY_TITLES["General"]) + INDUSTRY_TITLES["General"]
    return pick(rng, titles)


def _competitors(rng, industry):
    pool = COMPETITORS.get(industry, COMPETITORS["General"]) + COMPETITORS["General"]
    return rng.sample(list(dict.fromkeys(pool)), rng.randint(1, min(3, len(pool))))


def generate_personas(n=3, product="A digital product", industry="General", audience=None, locale="en-US", seed=None):
    audience = audience or []
    rng = make_rng(seed)
    personas = []

    for _ in range(n):
        gender_choice = pick_weighted(rng, [("female", 34), ("male", 34), ("neutral", 32)])
        first_name = pick(rng, FIRST_NAMES[gender_choice])
        last_name = pick(rng, LAST_NAMES)
        name = f"{first_name} {last_name}"
        age = _age_for_audience(rng, audience)
        pronouns = pick_weighted(rng, [("she/her", 34), ("he/him", 34), ("they/them", 32)])
        location = pick(rng, LOCATIONS)
        education = pick(rng, EDUCATION)
        family_status = pick(rng, FAMILY_STATUS)
        employment = pick(rng, EMPLOYMENT)
        role_title = _role_title(rng, industry)
        income = _income_range(rng, industry)
        tech = _tech_proficiency(rng, audience)
        accessibility = _accessibility_needs(rng)
        devices = _devices(rng)
        channels = pick_n(rng, CHANNELS, rng.randint(2, 4))
        archetype = pick(rng, ARCHETYPES)
        values = pick_n(rng, VALUES, 3)
        motivations = pick_n(rng, MOTIVATIONS, 3)
        frustrations = _frustrations(rng, industry)
        behaviors = _behaviors(rng, audience)
        goals = _goals(rng, product, industry)
        quote = _quote(rng, product)
        personality = _personality(rng)
        experience_with_competitors = _competitors(rng, industry)
        risk_aversion = clamp(rng.randint(1,5), 1, 5)
        preferred_support = pick_weighted(rng, [("Email", 30), ("Live chat", 30), ("Knowledge base", 20), ("Phone", 20)])

        persona = {
            "id": uid("persona"),
            "name": name,
            "age": age,
            "gender_identity": gender_choice,
            "pronouns": pronouns,
            "location": location,
            "role_title": role_title,
            "employment_status": employment,
            "income_range": income,
            "education": education,
            "family_status": family_status,
            "tech_proficiency": tech,
            "accessibility_needs": accessibility,
            "devices": devices,
            "preferred_channels": channels,
            "archetype": archetype,
            "values": values,
            "motivations": motivations,
            "goals": goals,
            "frustrations": frustrations,
            "behaviors": behaviors,
            "personality": personality,
            "quote": quote,
            "experience_with_competitors": experience_with_competitors,
            "risk_aversion": risk_aversion,
            "preferred_support": preferred_support
        }
        personas.append(persona)

    return personas

