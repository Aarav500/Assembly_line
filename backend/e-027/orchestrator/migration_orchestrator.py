from __future__ import annotations
import time
from typing import Any
from sqlalchemy.engine import Engine

from settings import settings
from orchestrator import alembic_utils
from orchestrator.prechecks import run_all_prechecks


class MigrationOrchestrator:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.cfg = alembic_utils.get_alembic_config()

    def plan(self) -> dict[str, Any]:
        pre = run_all_prechecks(self.engine)
        pending = alembic_utils.list_pending_revisions(self.engine, self.cfg)
        analyzed = alembic_utils.analyze_pending(self.engine, self.cfg)
        errors = []
        warnings = []
        for a in analyzed:
            errors.extend([{**e, "revision": a["revision"], "path": a["path"]}] for e in a["errors"])  # type: ignore
            warnings.extend([{**w, "revision": a["revision"], "path": a["path"]}] for w in a["warnings"])  # type: ignore
        cur = alembic_utils.get_current_revision(self.engine)
        heads = alembic_utils.get_head_revisions(self.cfg)
        return {
            "prechecks": pre,
            "current": cur,
            "heads": heads,
            "pending_count": len(pending),
            "pending": [{k: v for k, v in p.items() if k in ("revision", "down_revision", "doc", "path", "phase")} for p in pending],
            "analysis": analyzed,
            "errors": list(errors),
            "warnings": list(warnings),
        }

    def apply(self) -> dict[str, Any]:
        start = time.time()
        plan = self.plan()
        if not plan["prechecks"]["ok"]:
            return {"ok": False, "error": "Prechecks failed", "plan": plan}
        if settings.FAIL_ON_UNSAFE and plan["errors"]:
            return {"ok": False, "error": "Unsafe migration operations detected", "plan": plan}
        if not alembic_utils.acquire_advisory_lock(self.engine, settings.ADVISORY_LOCK_ID):
            return {"ok": False, "error": "Could not acquire advisory lock", "plan": plan}
        try:
            alembic_utils.upgrade_head(self.cfg)
            ok = True
            err = None
        except Exception as e:
            ok = False
            err = str(e)
        finally:
            alembic_utils.release_advisory_lock(self.engine, settings.ADVISORY_LOCK_ID)
        duration_ms = int((time.time() - start) * 1000)
        status = {
            "ok": ok,
            "error": err,
            "plan": plan,
            "duration_ms": duration_ms,
            "after_current": alembic_utils.get_current_revision(self.engine),
        }
        return status

