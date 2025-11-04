import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from flask import current_app
from .models import db, Idea, Policy


def get_effective_policy(idea: Idea) -> Optional[Policy]:
    pol = idea.policy
    if pol and pol.active:
        return pol
    # fallback: default policy
    return Policy.query.filter_by(name="default", active=True).first()


def should_archive(idea: Idea, now: datetime) -> bool:
    if idea.status != "active":
        return False
    if idea.expires_at is not None:
        return now >= idea.expires_at
    pol = get_effective_policy(idea)
    if pol and pol.auto_archive_after_days is not None:
        return now >= idea.created_at + timedelta(days=pol.auto_archive_after_days)
    return False


def should_purge(idea: Idea, now: datetime) -> Optional[bool]:
    # returns None if no purge policy, else bool indicating time reached
    if idea.status != "archived":
        return None
    pol = get_effective_policy(idea)
    if not pol or pol.auto_purge_after_days is None:
        return None
    if idea.archived_at is None:
        return None
    return now >= idea.archived_at + timedelta(days=pol.auto_purge_after_days)


def get_effective_purge_hard(idea: Idea) -> bool:
    if idea.purge_hard_override is not None:
        return idea.purge_hard_override
    pol = get_effective_policy(idea)
    if pol:
        return bool(pol.purge_hard)
    return bool(current_app.config.get("DEFAULT_PURGE_HARD", False))


def archive_idea(idea: Idea, when: datetime):
    idea.status = "archived"
    idea.archived_at = when
    db.session.add(idea)


def soft_purge_idea(idea: Idea, when: datetime):
    idea.status = "purged"
    idea.purged_at = when
    # Redact content on soft purge
    idea.content = None
    idea.title = f"[Purged #{idea.id}]"
    db.session.add(idea)


def hard_purge_idea(idea: Idea):
    db.session.delete(idea)


def run_maintenance_once(now: Optional[datetime] = None) -> dict:
    now = now or datetime.utcnow()
    archived = 0
    purged_soft = 0
    purged_hard = 0

    # Archive pass
    active_ideas = (
        Idea.query.filter(Idea.status == "active").order_by(Idea.id.asc()).all()
    )
    for idea in active_ideas:
        if should_archive(idea, now):
            archive_idea(idea, now)
            archived += 1
    db.session.commit()

    # Purge pass
    archived_ideas = (
        Idea.query.filter(Idea.status == "archived").order_by(Idea.id.asc()).all()
    )
    for idea in archived_ideas:
        sp = should_purge(idea, now)
        if sp:
            if get_effective_purge_hard(idea):
                hard_purge_idea(idea)
                purged_hard += 1
            else:
                soft_purge_idea(idea, now)
                purged_soft += 1
    db.session.commit()

    return {
        "archived": archived,
        "purged_soft": purged_soft,
        "purged_hard": purged_hard,
        "timestamp": now.isoformat() + "Z",
    }


def _scheduler_loop(app):
    interval = int(app.config.get("MAINTENANCE_INTERVAL_SECONDS", 60))
    while True:
        try:
            with app.app_context():
                run_maintenance_once()
        except Exception:
            # Avoid crashing the thread; errors are swallowed or could be logged
            pass
        time.sleep(max(1, interval))


def start_scheduler(app):
    if not app.config.get("SCHEDULER_ENABLED", True):
        return
    # Avoid starting twice under the reloader
    is_main = os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug
    if not is_main:
        return
    t = threading.Thread(target=_scheduler_loop, args=(app,), daemon=True)
    t.start()

