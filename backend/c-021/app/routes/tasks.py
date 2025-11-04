from datetime import timedelta, datetime
import json
import uuid
import time
from flask import Blueprint, request, jsonify, current_app
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from celery.result import AsyncResult
from app.celery_app import celery
from app.tasks import celery_tasks, rq_tasks

bp = Blueprint("tasks", __name__)


def _redis_conn():
    return Redis.from_url(current_app.config["REDIS_URL"])  # same URL for RQ and Celery Redis


def _rq_queue(name: str = None) -> Queue:
    return Queue(name or current_app.config.get("TASK_DEFAULT_QUEUE", "default"), connection=_redis_conn())


# ---------- Celery endpoints ----------
@bp.route("/tasks/celery/add", methods=["POST"]) 
def enqueue_celery_add():
    data = request.get_json(force=True, silent=True) or {}
    a = data.get("a")
    b = data.get("b")
    if a is None or b is None:
        return jsonify({"error": "Missing a or b"}), 400
    task = celery_tasks.add.apply_async(args=(a, b))
    return jsonify({"task_id": task.id})


@bp.route("/tasks/celery/long", methods=["POST"]) 
def enqueue_celery_long():
    data = request.get_json(force=True, silent=True) or {}
    duration = int(data.get("duration", 10))
    task = celery_tasks.long_task.apply_async(kwargs={"duration": duration}, countdown=int(data.get("countdown", 0)))
    return jsonify({"task_id": task.id})


@bp.route("/tasks/celery/schedule", methods=["POST"]) 
def schedule_celery_task():
    data = request.get_json(force=True, silent=True) or {}
    a = data.get("a", 1)
    b = data.get("b", 1)
    countdown = int(data.get("countdown", 30))
    eta_iso = data.get("eta")  # optional ISO datetime string
    if eta_iso:
        try:
            eta = datetime.fromisoformat(eta_iso)
        except Exception:
            return jsonify({"error": "Invalid eta"}), 400
        task = celery_tasks.add.apply_async(args=(a, b), eta=eta)
    else:
        task = celery_tasks.add.apply_async(args=(a, b), countdown=countdown)
    return jsonify({"task_id": task.id})


@bp.route("/tasks/celery/<task_id>", methods=["GET"]) 
def celery_status(task_id):
    res = AsyncResult(task_id, app=celery)
    payload = {"task_id": task_id, "state": res.state}
    try:
        info = res.info  # may be dict for progress
        if isinstance(info, dict):
            payload.update(info)
        elif info is not None:
            payload["info"] = str(info)
        if res.successful():
            payload["result"] = res.get(timeout=0)
    except Exception:
        pass
    return jsonify(payload)


# ---------- RQ endpoints ----------
@bp.route("/tasks/rq/add", methods=["POST"]) 
def enqueue_rq_add():
    data = request.get_json(force=True, silent=True) or {}
    a = data.get("a")
    b = data.get("b")
    if a is None or b is None:
        return jsonify({"error": "Missing a or b"}), 400
    q = _rq_queue()
    job = q.enqueue(rq_tasks.add, a, b)
    return jsonify({"job_id": job.id})


@bp.route("/tasks/rq/long", methods=["POST"]) 
def enqueue_rq_long():
    data = request.get_json(force=True, silent=True) or {}
    duration = int(data.get("duration", 10))
    delay = int(data.get("delay", 0))
    q = _rq_queue()
    if delay > 0:
        job = q.enqueue_in(timedelta(seconds=delay), rq_tasks.long_task, duration)
    else:
        job = q.enqueue(rq_tasks.long_task, duration)
    return jsonify({"job_id": job.id})


@bp.route("/tasks/rq/schedule", methods=["POST"]) 
def schedule_rq_task():
    data = request.get_json(force=True, silent=True) or {}
    a = data.get("a", 1)
    b = data.get("b", 1)
    delay = int(data.get("delay", 30))
    q = _rq_queue()
    job = q.enqueue_in(timedelta(seconds=delay), rq_tasks.add, a, b)
    return jsonify({"job_id": job.id})


@bp.route("/tasks/rq/<job_id>", methods=["GET"]) 
def rq_status(job_id):
    conn = _redis_conn()
    try:
        job = Job.fetch(job_id, connection=conn)
    except NoSuchJobError:
        return jsonify({"error": "Job not found", "job_id": job_id}), 404

    payload = {
        "job_id": job.id,
        "status": job.get_status(),
        "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        "meta": job.meta or {},
    }
    if job.is_finished:
        payload["result"] = job.result
    if job.is_failed:
        payload["exc_info"] = job.exc_info
    return jsonify(payload)


# ---------- Optional bridges (best-effort) ----------
# NOTE: These are minimal Redis-based enqueuers for external ecosystems.
# Sidekiq: pushes a job payload to queue:<queue_name>. Requires a Ruby worker class present downstream.
@bp.route("/bridge/sidekiq/enqueue", methods=["POST"]) 
def bridge_sidekiq_enqueue():
    data = request.get_json(force=True, silent=True) or {}
    queue = data.get("queue", "default")
    class_name = data.get("class") or data.get("class_name") or "HardJob"
    args = data.get("args", [])
    jid = data.get("jid") or uuid.uuid4().hex
    now = time.time()
    payload = {
        "class": class_name,
        "args": args,
        "jid": jid,
        "retry": True,
        "queue": queue,
        "created_at": now,
        "enqueued_at": now,
    }
    key = f"queue:{queue}"
    _redis_conn().rpush(key, json.dumps(payload))
    return jsonify({"enqueued": True, "queue": key, "jid": jid, "note": "This aims at Sidekiq's simple job format."})


# Bull: Not a drop-in; returns 501 to indicate unimplemented protocol-specific enqueue.
@bp.route("/bridge/bull/enqueue", methods=["POST"]) 
def bridge_bull_enqueue():
    return jsonify({"error": "Bull protocol is not implemented in Python scaffold. Use a Node/Bull producer."}), 501

