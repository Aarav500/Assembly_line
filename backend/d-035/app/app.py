import threading
from datetime import datetime

from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from .config import settings
from . import storage
from .job import recheck_all_images


scheduler: BackgroundScheduler | None = None
_job_lock = threading.Lock()
_is_running = False


def _scan_job_wrapper():
    global _is_running
    if not _job_lock.acquire(blocking=False):
        return
    try:
        if _is_running:
            return
        _is_running = True
        recheck_all_images()
    finally:
        _is_running = False
        _job_lock.release()


def create_app() -> Flask:
    app = Flask(__name__)

    storage.init_db()

    tz = pytz.timezone(settings.timezone)
    global scheduler
    scheduler = BackgroundScheduler(timezone=tz)

    # Configure cron trigger from settings.SCHEDULE_CRON ("min hr dom mon dow")
    parts = settings.schedule_cron.split()
    if len(parts) != 5:
        # fallback to daily at 03:00
        trigger = CronTrigger(hour=3, minute=0, timezone=tz)
    else:
        minute, hour, day, month, day_of_week = parts
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=tz,
        )

    scheduler.add_job(
        _scan_job_wrapper,
        trigger=trigger,
        id="cve_recheck",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()

    @app.route("/health", methods=["GET"])  # Simple health check
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/images", methods=["GET"])  # Configured images
    def api_images():
        return jsonify({"images": settings.load_images()})

    @app.route("/api/status", methods=["GET"])  # Scheduler status
    def api_status():
        job = scheduler.get_job("cve_recheck") if scheduler else None
        next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
        return jsonify(
            {
                "schedule_cron": settings.schedule_cron,
                "timezone": settings.timezone,
                "next_run": next_run,
                "running": _is_running,
            }
        )

    @app.route("/api/recheck", methods=["POST"])  # Manual trigger
    def api_recheck():
        # Optionally accept subset of images to scan in body
        # For simplicity, always run full recheck in background thread
        def run_async():
            _scan_job_wrapper()

        threading.Thread(target=run_async, daemon=True).start()
        return jsonify({"status": "scheduled", "requested_at": datetime.utcnow().isoformat()})

    @app.route("/api/scans", methods=["GET"])  # Recent scans or latest per image
    def api_scans():
        mode = request.args.get("mode", "recent")
        if mode == "latest":
            scans = storage.get_latest_scans_by_image()
        else:
            limit = int(request.args.get("limit", "100"))
            scans = storage.get_recent_scans(limit=limit)
        return jsonify({"scans": scans})

    @app.route("/api/scans/<path:image>", methods=["GET"])  # Scans for specific image
    def api_scans_for_image(image: str):
        limit = int(request.args.get("limit", "50"))
        scans = storage.get_scans_for_image(image=image, limit=limit)
        return jsonify({"image": image, "scans": scans})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=settings.flask_host, port=settings.flask_port, debug=settings.debug)

