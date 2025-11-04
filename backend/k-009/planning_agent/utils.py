from __future__ import annotations
from typing import Dict, List
import re


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def estimate_complexity(goal: str) -> float:
    # Simple heuristic: longer goals and more verbs => higher complexity
    length_score = min(len(goal) / 120.0, 2.0)
    verbs = len(re.findall(r'\b(build|create|write|develop|research|analyze|deploy|fix|migrate|design)\b', goal.lower()))
    verb_score = min(verbs * 0.3, 2.0)
    return max(0.8, 1.0 + length_score + verb_score)


def infer_resources(goal: str) -> Dict[str, List[str]]:
    g = goal.lower()
    tools: List[str] = []
    skills: List[str] = []
    materials: List[str] = []

    if any(k in g for k in ["python", "api", "flask", "backend", "server", "code", "script", "program"]):
        tools += ["Python 3", "pip/venv", "Git", "Editor/IDE", "HTTP client"]
        skills += ["Software design", "Python", "REST/HTTP", "Testing"]
    if any(k in g for k in ["data", "analysis", "model", "ml", "analytics"]):
        tools += ["Jupyter", "Pandas", "NumPy"]
        skills += ["Data analysis", "Visualization"]
    if any(k in g for k in ["write", "document", "content", "blog", "readme"]):
        tools += ["Markdown editor", "Style guide"]
        skills += ["Technical writing"]
    if any(k in g for k in ["deploy", "release", "prod", "production", "cloud"]):
        tools += ["CI/CD", "Containerization", "Monitoring"]
        skills += ["DevOps", "Monitoring"]

    if not tools:
        tools = ["Task tracker", "Notes/Wiki"]
    if not skills:
        skills = ["Planning", "Communication"]

    return {"tools": sorted(set(tools)), "skills": sorted(set(skills)), "materials": materials}


def default_step_names(goal: str) -> List[str]:
    names = [
        "Define Objectives & Success Criteria",
        "Gather Information & Resources",
        "Plan Approach & Milestones",
        "Execute Core Work",
        "Review, Test, and Iterate",
        "Finalize & Deliver",
        "Post-Delivery Follow-up",
    ]
    g = goal.lower()
    if any(k in g for k in ["deploy", "release", "publish"]):
        names.insert(5, "Deployment & Monitoring")
    return names

