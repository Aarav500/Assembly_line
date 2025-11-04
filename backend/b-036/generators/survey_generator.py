import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import random


LIKERT5 = [
    {"value": 1, "label": "Strongly disagree"},
    {"value": 2, "label": "Disagree"},
    {"value": 3, "label": "Neutral"},
    {"value": 4, "label": "Agree"},
    {"value": 5, "label": "Strongly agree"}
]

LIKERT7 = [
    {"value": 1, "label": "Strongly disagree"},
    {"value": 2, "label": "Disagree"},
    {"value": 3, "label": "Slightly disagree"},
    {"value": 4, "label": "Neutral"},
    {"value": 5, "label": "Slightly agree"},
    {"value": 6, "label": "Agree"},
    {"value": 7, "label": "Strongly agree"}
]


def _coalesce(val, default):
    return val if val is not None else default


def _safe_list(x):
    if isinstance(x, list):
        return x
    if x is None:
        return []
    return [x]


def _scale(scale_type: str):
    return LIKERT7 if str(scale_type).lower() == "likert7" else LIKERT5


def _length_to_counts(length: str) -> Dict[str, int]:
    l = (length or "medium").lower()
    if l == "short":
        return {"per_feature": 2, "global": 3}
    if l == "long":
        return {"per_feature": 4, "global": 5}
    return {"per_feature": 3, "global": 4}


def _feature_questions(feature: str, scale, rng: random.Random, n: int) -> List[Dict[str, Any]]:
    items = []
    templates = [
        ("likert", f"It was easy to accomplish what I wanted using {feature}."),
        ("likert", f"I could quickly find the {feature} I needed."),
        ("likert", f"The {feature} works as I expected."),
        ("open_ended", f"What, if anything, was confusing about {feature}?") ,
        ("rating", f"Rate your satisfaction with {feature}.")
    ]
    rng.shuffle(templates)
    for t, text in templates[:n]:
        if t == "likert":
            items.append({
                "type": "likert",
                "text": text,
                "required": True,
                "scale": scale
            })
        elif t == "rating":
            items.append({
                "type": "rating",
                "text": text,
                "required": True,
                "min": 1,
                "max": 10,
                "labels": {"min": "Very dissatisfied", "max": "Very satisfied"}
            })
        else:
            items.append({
                "type": "open_ended",
                "text": text,
                "required": False,
                "placeholder": "Your feedback..."
            })
    return items


def _global_questions(scale, rng: random.Random, n: int) -> List[Dict[str, Any]]:
    templates = [
        {"type": "likert", "text": "Overall, the product is easy to use.", "required": True, "scale": scale},
        {"type": "likert", "text": "I can accomplish my goals efficiently.", "required": True, "scale": scale},
        {"type": "likert", "text": "I feel confident using this product.", "required": True, "scale": scale},
        {"type": "multiple_choice", "text": "Which areas need the most improvement?", "required": False, "options": ["Navigation", "Performance", "Content clarity", "Visual design", "Accessibility", "Other"]},
        {"type": "open_ended", "text": "If you could change one thing, what would it be?", "required": False, "placeholder": "Your suggestion..."}
    ]
    rng.shuffle(templates)
    return templates[:n]


def _demographics(include: bool) -> List[Dict[str, Any]]:
    if not include:
        return []
    return [
        {"type": "demographic", "text": "Age", "required": False, "options": ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]},
        {"type": "demographic", "text": "Experience level with similar products", "required": False, "options": ["New", "Intermediate", "Advanced"]},
        {"type": "demographic", "text": "Primary platform", "required": False, "options": ["Web", "iOS", "Android", "Desktop"]}
    ]


def _screeners(include: bool, features: List[str]) -> List[Dict[str, Any]]:
    if not include:
        return []
    return [
        {"type": "single_choice", "text": "Have you used a product like this in the last 3 months?", "required": True, "options": ["Yes", "No"]},
        {"type": "multiple_choice", "text": "Which of the following tasks have you done recently?", "required": False, "options": [f for f in features] or ["Browsing", "Searching", "Purchasing"]}
    ]


def _estimate_time(num_questions: int) -> int:
    # Approximate: 20-30s for fixed-choice, 60s for open-ended
    fixed = 0
    open_ended = 0
    for i in range(num_questions):
        fixed += 1
    # Simple: assume 1/5 open-ended
    open_ended = max(1, num_questions // 5)
    return int(fixed * 0.5 + open_ended * 1.0)


def _assign_ids(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for idx, q in enumerate(questions, start=1):
        q_copy = {**q}
        q_copy["id"] = f"q{idx}"
        out.append(q_copy)
    return out


def generate_survey(payload: Dict[str, Any]) -> Dict[str, Any]:
    seed = payload.get("seed")
    rng = random.Random(seed)
    survey_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    title = payload.get("title") or "User Experience Survey"
    survey_purpose = payload.get("survey_purpose") or "Collect feedback on usability and satisfaction."
    target_users = _safe_list(payload.get("target_users")) or ["target users"]
    features = _safe_list(payload.get("features")) or ["onboarding", "navigation", "search"]
    include_demographics = bool(payload.get("include_demographics", True))
    include_screening = bool(payload.get("include_screening", False))
    length = (payload.get("length") or "medium").lower()
    scale_type = (payload.get("scale_type") or "likert5").lower()

    scale = _scale(scale_type)
    counts = _length_to_counts(length)

    questions: List[Dict[str, Any]] = []

    # Screeners (if any)
    questions.extend(_screeners(include_screening, features))

    # Global questions
    questions.extend(_global_questions(scale, rng, counts["global"]))

    # Feature-specific blocks
    for f in features:
        questions.append({"type": "section", "text": f"About {f}"})
        questions.extend(_feature_questions(f, scale, rng, counts["per_feature"]))

    # Demographics
    questions.extend(_demographics(include_demographics))

    # Branching example: If user selects Other in improvement, ask follow-up
    questions.append({
        "type": "open_ended",
        "text": "Please describe the 'Other' area you selected.",
        "required": False,
        "visible_if": {"question_ref_text_contains": "Which areas need the most improvement?", "option": "Other"}
    })

    questions = _assign_ids(questions)

    estimated_time_minutes = _estimate_time(len(questions))

    survey = {
        "metadata": {
            "id": survey_id,
            "generated_at": now,
            "seed": seed
        },
        "title": title,
        "purpose": survey_purpose,
        "target_users": target_users,
        "instructions": "Please answer honestly based on your experience. There are no right or wrong answers.",
        "estimated_time_minutes": estimated_time_minutes,
        "questions": questions,
        "thank_you": "Thanks for your time and feedback!"
    }

    return {
        "id": survey_id,
        "generated_at": now,
        "survey": survey
    }

