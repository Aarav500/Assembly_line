import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import random


DEFAULT_TOOLS = ["Zoom", "Lookback", "Figma", "Loom"]
DEFAULT_LANG = ["en"]


def _coalesce(val, default):
    return val if val is not None else default


def _safe_list(x):
    if isinstance(x, list):
        return x
    if x is None:
        return []
    return [x]


def _pick_session_type(constraints: Dict[str, Any]) -> str:
    t = (constraints or {}).get("session_type")
    if t in {"remote", "in_person", "unmoderated"}:
        return t
    return "remote"


def _pick_tools(constraints: Dict[str, Any]) -> List[str]:
    tools = _safe_list((constraints or {}).get("tools"))
    return tools if tools else DEFAULT_TOOLS


def _duration(constraints: Dict[str, Any]) -> int:
    dur = (constraints or {}).get("max_duration_minutes")
    if isinstance(dur, int) and 20 <= dur <= 120:
        return dur
    return 60


def _languages(constraints: Dict[str, Any]) -> List[str]:
    langs = _safe_list((constraints or {}).get("languages"))
    return langs if langs else DEFAULT_LANG


def _default_participants(participants: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    participants = participants or {}
    count = participants.get("count")
    if not isinstance(count, int) or count <= 0:
        count = 6
    segs = participants.get("segments") or []
    if not segs:
        segs = [{"name": "general target users", "count": count}]
    return {"count": count, "segments": segs}


def _prioritize(idx: int, total: int) -> str:
    if idx < max(1, total // 3):
        return "critical"
    if idx < max(2, 2 * total // 3):
        return "high"
    return "medium"


def _scenario_from_feature(feature: str, idx: int, total: int, platforms: List[str]) -> Dict[str, Any]:
    priority = _prioritize(idx, total)
    return {
        "title": f"Complete a typical task using {feature}",
        "feature": feature,
        "priority": priority,
        "platforms": platforms,
        "task": f"Using the {feature} capability, accomplish a representative goal you would do in real life.",
        "success_criteria": [
            "Participant completes the task without external help",
            "No critical usability issues encountered",
            "Completion time within acceptable range"
        ],
        "data_to_capture": [
            "Time on task",
            "Task success/failure",
            "Errors and recovery",
            "Verbal comments and emotional valence"
        ],
        "observations_template": [
            "What worked well?",
            "Where did the participant hesitate?",
            "Confusions or errors?",
            "Mental model misalignments?"
        ]
    }


def _core_metrics(success_metrics: List[str]) -> Dict[str, Any]:
    return {
        "qualitative": [
            "Observed usability issues categorized by severity",
            "Participant quotes supporting key findings",
            "Perceived ease of use per task"
        ],
        "quantitative": [
            "Task success rate",
            "Time on task",
            "Error rate",
            "Post-task confidence"
        ],
        "study_success_criteria": success_metrics or [
            ">=80% task success on critical tasks",
            ">=70 System Usability Scale (SUS)"
        ]
    }


def _analysis_plan() -> Dict[str, Any]:
    return {
        "approach": [
            "Affinity mapping for qualitative themes",
            "Severity rating using a 0-4 scale",
            "Descriptive statistics for quantitative metrics"
        ],
        "triangulation": [
            "Cross-compare behaviors across segments",
            "Contrast intended vs. actual paths",
            "Validate findings against goals"
        ],
        "reporting": [
            "Executive summary with top issues and recommendations",
            "Detailed findings per task",
            "Appendix with raw notes and metrics"
        ]
    }


def _session_script(product_name: str, duration: int) -> Dict[str, Any]:
    return {
        "intro": [
            f"Thank you for joining. We'll be looking at {product_name}.",
            "We are testing the product, not you.",
            "Think aloud as you go."
        ],
        "warm_up": ["Tell me about the last time you did a similar task."] ,
        "during_tasks": [
            "Remind: Think aloud.",
            "Neutral prompts: What are you thinking? What would you do next?"
        ],
        "wrap_up": [
            "Overall impressions and satisfaction",
            "Top 3 frustrations and delights",
            "Any missing capabilities?"
        ],
        "timing_breakdown_minutes": {
            "intro": 5,
            "warm_up": 5,
            "tasks": max(10, duration - 15),
            "wrap_up": 5
        }
    }


def _risks_and_mitigations() -> List[Dict[str, Any]]:
    return [
        {"risk": "Participants stray off-task", "mitigation": "Use clear task prompts and neutral nudges"},
        {"risk": "Technical issues in remote setup", "mitigation": "Backup conferencing tool and contingency plan"},
        {"risk": "Prototype instability", "mitigation": "Have alternate paths and screenshots ready"}
    ]


def _materials(tools: List[str]) -> List[str]:
    return [
        "Consent form",
        "Moderator guide",
        "Task sheets",
        "Recording setup",
        f"Tools: {', '.join(tools)}"
    ]


def generate_test_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    seed = payload.get("seed")
    rng = random.Random(seed)
    plan_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    product_name = payload.get("product_name") or "Your Product"
    version = payload.get("version") or "N/A"
    goals = _safe_list(payload.get("goals")) or [
        "Identify major usability issues",
        "Validate discoverability of key features"
    ]
    target_users = _safe_list(payload.get("target_users")) or ["target customers"]
    features = _safe_list(payload.get("features")) or ["onboarding", "navigation", "search"]
    platforms = _safe_list(payload.get("platforms")) or ["web"]

    constraints = payload.get("constraints") or {}
    session_type = _pick_session_type(constraints)
    tools = _pick_tools(constraints)
    duration = _duration(constraints)
    languages = _languages(constraints)

    participants = _default_participants(payload.get("participants"))
    timeline = payload.get("timeline") or {}

    success_metrics = _safe_list(payload.get("success_metrics"))

    # Shuffle features if requested via seed to vary task order while deterministic under seed
    features_shuffled = features[:]
    rng.shuffle(features_shuffled)

    scenarios = [
        _scenario_from_feature(f, i, len(features_shuffled), platforms)
        for i, f in enumerate(features_shuffled)
    ]

    plan = {
        "metadata": {
            "id": plan_id,
            "generated_at": now,
            "product_name": product_name,
            "version": version,
            "language": languages[0],
            "seed": seed
        },
        "overview": {
            "title": f"Usability Test Plan - {product_name}",
            "goals": goals,
            "methodology": {
                "session_type": session_type,
                "moderation": "moderated" if session_type != "unmoderated" else "unmoderated",
                "platforms": platforms,
                "tools": tools,
                "languages": languages
            },
            "timeline": {
                "start": timeline.get("start", "TBD"),
                "end": timeline.get("end", "TBD")
            }
        },
        "participants": {
            "profile_summary": target_users,
            "recruitment_plan": {
                "total": participants["count"],
                "segments": participants["segments"],
                "incentive": payload.get("incentive", "$75 gift card"),
                "screening_notes": "Focus on users with experience relevant to features under test."
            }
        },
        "session": {
            "duration_minutes": duration,
            "locations": "remote" if session_type == "remote" else "lab/office",
            "materials": _materials(tools),
            "consent": {
                "required": True,
                "data_policy": "Recordings are used only for research and will be stored securely."
            },
            "script": _session_script(product_name, duration)
        },
        "scenarios": scenarios,
        "metrics": _core_metrics(success_metrics),
        "analysis_plan": _analysis_plan(),
        "risks_and_mitigations": _risks_and_mitigations(),
        "deliverables": [
            "Executive summary",
            "Prioritized issues list",
            "Recommendations",
            "Annotated recordings and transcripts"
        ],
        "note_taking_template": {
            "participant_id": "P#",
            "segment": "",
            "task_notes": [
                {"feature": s["feature"], "observations": [], "issues": [], "time_on_task": None, "success": None}
                for s in scenarios
            ],
            "overall_feedback": {"positives": [], "frustrations": [], "suggestions": []}
        }
    }

    return {
        "id": plan_id,
        "generated_at": now,
        "plan": plan
    }

