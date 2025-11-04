import math
import time
from datetime import datetime
from flask import jsonify, request, current_app

from jobs import tasks


def _now_iso():
    tz = current_app.config.get("TIMEZONE")
    return datetime.now(tz).isoformat()


def register_routes(app):
    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "timestamp": _now_iso()})

    @app.get("/echo")
    def echo():
        msg = request.args.get("msg", "hello")
        return jsonify({"message": msg, "timestamp": _now_iso()})

    @app.get("/compute")
    def compute():
        # Do some CPU work to simulate non-trivial processing
        x = int(request.args.get("x", 2000))
        # Sum of square roots 1..x as a simple workload
        s = 0.0
        for i in range(1, x + 1):
            s += math.sqrt(i)
        return jsonify({"input": x, "result": s, "timestamp": _now_iso()})

    @app.get("/jobs")
    def list_jobs():
        sched = app.extensions.get("scheduler")
        if not sched:
            return jsonify({"jobs": []})
        jobs_info = []
        for j in sched.get_jobs():
            jobs_info.append({
                "id": j.id,
                "name": j.name,
                "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                "trigger": str(j.trigger),
            })
        return jsonify({"jobs": jobs_info})

    @app.post("/jobs/run/integration")
    def trigger_integration_now():
        sched = app.extensions.get("scheduler")
        if not sched:
            return jsonify({"error": "scheduler not initialized"}), 500
        ts = tasks.timestamp(app.config["TIMEZONE"])  # YYYYmmdd_HHMMSS
        job_id = f"manual_integration_{ts}"
        sched.add_job(
            func=tasks.integration_tests_job,
            trigger="date",
            args=[app._get_current_object()],
            id=job_id,
            replace_existing=False,
        )
        return jsonify({"scheduled": job_id})

    @app.post("/jobs/run/load")
    def trigger_load_now():
        sched = app.extensions.get("scheduler")
        if not sched:
            return jsonify({"error": "scheduler not initialized"}), 500
        ts = tasks.timestamp(app.config["TIMEZONE"])  # YYYYmmdd_HHMMSS
        job_id = f"manual_load_{ts}"
        sched.add_job(
            func=tasks.load_tests_job,
            trigger="date",
            args=[app._get_current_object()],
            id=job_id,
            replace_existing=False,
        )
        return jsonify({"scheduled": job_id})

