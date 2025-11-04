from .utils import make_rng, uid, pick, pick_weighted, clamp, now_iso, slugify

TOUCHPOINTS = [
    ("Mobile app", 40), ("Website", 35), ("Email", 10), ("Social media", 7), ("Help center", 5), ("Phone support", 3)
]

CHANNELS = [
    ("In-app", 45), ("Web", 35), ("Email", 12), ("SMS", 8)
]

EMOTIONS = [
    ("Delighted", 3), ("Happy", 2), ("Neutral", 0), ("Frustrated", -2), ("Anxious", -1), ("Confident", 1), ("Blocked", -3)
]

COMMON_PAIN_POINTS = [
    "Confusing navigation", "Long forms", "Unclear pricing", "Slow loading", "Integration failures",
    "Unhelpful error messages", "Verification delays", "Hidden settings"
]

COMMON_OPPORTUNITIES = [
    "Shorten steps", "Add progress indicators", "Improve copywriting", "Provide defaults/templates",
    "Offer live chat help", "Save progress automatically", "Integrate with popular tools"
]

DEFAULT_STAGE_HINTS = {
    "Awareness": [
        ("Sees an ad or a peer recommendation", 0.5),
        ("Searches for solutions and reads top results", 0.5)
    ],
    "Consideration": [
        ("Compares features and pricing pages", 0.6),
        ("Reads third-party reviews and case studies", 0.4)
    ],
    "Onboarding": [
        ("Creates account and verifies email", 0.5),
        ("Completes profile and selects preferences", 0.5)
    ],
    "Activation": [
        ("Completes first key action successfully", 0.7),
        ("Explores core feature guided by tips", 0.3)
    ],
    "Retention": [
        ("Receives tips and uses product weekly", 0.5),
        ("Shares feedback or invites a teammate", 0.5)
    ]
}

FINTECH_STAGE_HINTS = {
    "Awareness": [
        ("Hears about faster invoicing in a freelancer forum", 0.6),
        ("Sees a YouTube creator mention bank syncs", 0.4)
    ],
    "Onboarding": [
        ("Connects bank account via aggregator", 0.6),
        ("Sets up tax category rules", 0.4)
    ],
    "Activation": [
        ("Sends first invoice and tracks payment", 0.6),
        ("Categorizes last month transactions", 0.4)
    ]
}


def _stage_hints(industry):
    hints = {k: v[:] for k, v in DEFAULT_STAGE_HINTS.items()}
    if industry.lower() == "fintech":
        for stage, extra in FINTECH_STAGE_HINTS.items():
            hints.setdefault(stage, [])
            hints[stage].extend(extra)
    return hints


def _gen_step(rng, stage_name, scenario, product, industry):
    touchpoint = pick_weighted(rng, TOUCHPOINTS)
    channel = pick_weighted(rng, CHANNELS)
    feeling_label, feeling_val = pick_weighted(rng, [(e, 1) for e in [x[0] for x in EMOTIONS]]), None
    # map to valence
    feeling_val = next((v for e, v in EMOTIONS if e == feeling_label), 0)

    # craft action
    action_templates = {
        "Awareness": [
            f"Notices {product} while researching {industry} tools",
            f"Clicks a post comparing {product} with a competitor"
        ],
        "Consideration": [
            f"Skims pricing, checks limits, and reads FAQs",
            f"Watches a 2-minute demo highlighting key flows"
        ],
        "Onboarding": [
            "Starts sign-up, verifies email, sets password",
            "Accepts permissions and configures basic settings"
        ],
        "Activation": [
            f"Uses a core feature related to '{scenario}'",
            "Creates and completes a first task successfully"
        ],
        "Retention": [
            "Returns after a few days, completes a routine task",
            "Receives a helpful tip via email and tries it"
        ]
    }

    pains = rng.sample(COMMON_PAIN_POINTS, rng.randint(0, 2))
    opps = rng.sample(COMMON_OPPORTUNITIES, rng.randint(1, 3))

    # time spent roughly by stage
    t_map = {"Awareness": (5, 60), "Consideration": (30, 240), "Onboarding": (120, 600), "Activation": (60, 420), "Retention": (30, 180)}
    t_bounds = t_map.get(stage_name, (30, 180))
    time_spent = rng.randint(*t_bounds)

    # success prob influenced by pains and valence
    base_success = 0.82 if stage_name in ("Activation", "Retention") else 0.7
    base_success -= 0.08 * len(pains)
    base_success += 0.03 * max(0, feeling_val)
    success_prob = clamp(round(base_success, 2), 0.05, 0.98)

    dropoff = clamp(round(1 - success_prob + (0.02 * len(pains)), 2), 0.0, 1.0)

    # craft text variations
    action = pick(rng, action_templates.get(stage_name, [f"Progresses through {stage_name.lower()} stage"]))

    thoughts = pick(rng, [
        "This looks promising, but is it worth switching?",
        "I hope this setup doesn't take forever.",
        "I just want to finish this quickly.",
        "This part is smoother than I expected.",
        "Why is this step asking for so much info?"
    ])

    system_response = pick(rng, [
        "Loads content quickly and shows relevant next steps",
        "Shows clear CTA and short explainer",
        "Displays progress with helpful hints",
        "Returns a generic error that suggests trying again",
        "Confirms success and highlights next action"
    ])

    step = {
        "user_action": action,
        "touchpoint": touchpoint,
        "channel": channel,
        "system_response": system_response,
        "thoughts": thoughts,
        "feeling": {"label": feeling_label, "valence": feeling_val},
        "pain_points": pains,
        "opportunities": opps,
        "metrics": {
            "time_spent_sec": time_spent,
            "success_probability": success_prob
        },
        "drop_off_risk": dropoff
    }
    return step


def _specialize_step_for_industry(step, stage_name, industry, scenario):
    # Light specialization for realism
    if industry.lower() == "fintech" and stage_name in ("Onboarding", "Activation"):
        if "permissions" in step["user_action"].lower() or stage_name == "Onboarding":
            step["user_action"] = "Connects bank account and grants read-only access"
            step["system_response"] = "Redirects to secure aggregator, returns and confirms connection"
            step["pain_points"] = list(set(step["pain_points"] + ["Integration failures"]))[:3]
            step["opportunities"] = list(set(step["opportunities"] + ["Offer live chat help"]))[:3]
        elif stage_name == "Activation":
            step["user_action"] = "Sends first invoice and shares payment link"
            step["system_response"] = "Shows invoice preview and tracks payment status"
    return step


def generate_journeys(personas, scenario, stages, journeys_per_persona, product, industry, seed=None):
    rng = make_rng(seed)
    stage_hints = _stage_hints(industry)

    results = []
    for persona in personas:
        for _ in range(journeys_per_persona):
            journey_id = uid("journey")
            steps_all = []
            for s_idx, stage_name in enumerate(stages, start=1):
                # build 1-2 steps per stage
                step_count = 2 if stage_name in ("Onboarding", "Activation") else 1
                steps = []
                for i in range(step_count):
                    step = _gen_step(rng, stage_name, scenario, product, industry)
                    step = _specialize_step_for_industry(step, stage_name, industry, scenario)
                    step["step_number"] = i + 1
                    steps.append(step)
                # try to align one step with stage hint for flavor
                hints = stage_hints.get(stage_name, [])
                if hints and rng.random() < 0.75:
                    hint_text = pick_weighted(rng, hints)
                    steps[0]["user_action"] = hint_text
                stage = {
                    "name": stage_name,
                    "stage_index": s_idx,
                    "steps": steps
                }
                steps_all.append(stage)

            # aggregate metrics
            total_time = sum(stp["metrics"]["time_spent_sec"] for stg in steps_all for stp in stg["steps"])
            avg_success = round(sum(stp["metrics"]["success_probability"] for stg in steps_all for stp in stg["steps"]) / sum(len(stg["steps"]) for stg in steps_all), 3)
            avg_dropoff = round(sum(stp["drop_off_risk"] for stg in steps_all for stp in stg["steps"]) / sum(len(stg["steps"]) for stg in steps_all), 3)

            journey = {
                "id": journey_id,
                "persona_id": persona["id"],
                "scenario": scenario,
                "product": product,
                "industry": industry,
                "created_at": now_iso(),
                "stages": steps_all,
                "summary": {
                    "total_time_sec": total_time,
                    "avg_step_success_probability": avg_success,
                    "avg_step_drop_off_risk": avg_dropoff
                },
                "tags": [slugify(industry), slugify(product)][:5]
            }
            results.append(journey)
    return results

