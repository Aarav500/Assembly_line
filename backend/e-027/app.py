import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from __future__ import annotations
from flask import Flask, jsonify, request
from db import get_engine
from orchestrator.migration_orchestrator import MigrationOrchestrator
from orchestrator import alembic_utils
from settings import settings

app = Flask(__name__)


@app.get("/healthz")
def healthz():
    try:
        with get_engine().connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/migrate/status")
def migrate_status():
    engine = get_engine()
    orch = MigrationOrchestrator(engine)
    plan = orch.plan()
    return jsonify({
        "current": plan.get("current"),
        "heads": plan.get("heads"),
        "pending_count": plan.get("pending_count"),
        "prechecks_ok": plan.get("prechecks", {}).get("ok"),
        "warnings": plan.get("warnings"),
        "errors": plan.get("errors"),
    })


@app.post("/migrate/plan")
def migrate_plan():
    engine = get_engine()
    orch = MigrationOrchestrator(engine)
    return jsonify(orch.plan())


@app.post("/migrate/apply")
def migrate_apply():
    engine = get_engine()
    orch = MigrationOrchestrator(engine)
    result = orch.apply()
    code = 200 if result.get("ok") else 400
    return jsonify(result), code


@app.post("/migrate/precheck")
def migrate_precheck():
    engine = get_engine()
    from orchestrator.prechecks import run_all_prechecks
    res = run_all_prechecks(engine)
    code = 200 if res.get("ok") else 400
    return jsonify(res), code


@app.post("/lock/acquire")
def lock_acquire():
    engine = get_engine()
    ok = alembic_utils.acquire_advisory_lock(engine, settings.ADVISORY_LOCK_ID)
    return jsonify({"ok": ok, "lock_id": settings.ADVISORY_LOCK_ID}), (200 if ok else 409)


@app.post("/lock/release")
def lock_release():
    engine = get_engine()
    ok = alembic_utils.release_advisory_lock(engine, settings.ADVISORY_LOCK_ID)
    return jsonify({"ok": ok, "lock_id": settings.ADVISORY_LOCK_ID})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT, debug=settings.DEBUG)



def create_app():
    return app
