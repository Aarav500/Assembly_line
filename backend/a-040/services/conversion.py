from typing import Tuple, Optional
from flask import current_app
from extensions import db
from models import Project, Idea, IdeaFeature


STATUS_MAP = {
    "active": "draft",
    "paused": "backlog",
    "archived": "icebox",
}

PRIORITY_TO_IMPACT = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def map_status(project_status: Optional[str]) -> str:
    if not project_status:
        return "draft"
    key = project_status.strip().lower()
    return STATUS_MAP.get(key, "draft")


def map_priority_to_impact(priority: Optional[str]) -> str:
    if not priority:
        return "Medium"
    return PRIORITY_TO_IMPACT.get(priority.strip().lower(), "Medium")


def convert_project_to_idea(project_id: int) -> Tuple[Optional[Idea], bool]:
    project = Project.query.get(project_id)
    if not project:
        return None, False

    # Idempotency: if an Idea already exists for this project, return it.
    existing = Idea.query.filter_by(source_project_id=project.id).order_by(Idea.created_at.desc()).first()
    if existing:
        return existing, False

    idea = Idea(
        title=project.name,
        summary=project.description or "",
        problem=f"Derived from project '{project.name}'.",
        solution="",  # intentionally left for ideation post-conversion
        status=map_status(project.status),
        source_project_id=project.id,
    )

    # Copy tags
    idea.tags = list(project.tags) if project.tags else []

    # Map features
    for pf in project.features:
        idea.features.append(
            IdeaFeature(
                name=pf.name,
                description=pf.description or "",
                impact=map_priority_to_impact(pf.priority),
            )
        )

    db.session.add(idea)
    db.session.commit()

    current_app.logger.info("Converted project %s -> idea %s", project.id, idea.id)
    return idea, True

