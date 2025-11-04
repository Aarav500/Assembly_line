import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time
import uuid
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, request

from config import settings
from redis_client import get_redis

app = Flask(__name__)


QUEUE_KEY = settings.queue_key


def _now() -> float:
    return time.time()


def _job_key(job_id: str) -> str:
    return f"webhook:job:{job_id}"


def _status_key(event_id: str) -> str:
    return f"webhook:status:{event_id}"


def _history_key(event_id: str) -> str:
    return f"webhook:history:{event_id}"


def _to_json_str(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, separators=(",", ":"))


def enqueue_webhook(
    target_url: str,
    payload: Any,
    headers: Optional[Dict[str, str]] = None,
    event_id: Optional[str] = None,
    max_attempts: Optional[int] = None,
    backoff: Optional[Dict[str, Any]] = None,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    r = get_redis()

    if not event_id:
        event_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    # Determine if payload is JSON; store as string
    is_json = not isinstance(payload, str)
    body_json = payload if is_json else None
    body_str = payload if isinstance(payload, str) else _to_json_str(payload)

    # Defaults
    max_attempts = max_attempts or settings.default_max_attempts
    backoff = backoff or {}
    b_base = float(backoff.get("base", settings.backoff_base))
    b_factor = float(backoff.get("factor", settings.backoff_factor))
    b_jitter = float(backoff.get("jitter", settings.backoff_jitter))
    b_max = float(backoff.get("max", settings.backoff_max))

    # Normalize headers
    headers = headers or {}

    job_data = {
        "job_id": job_id,
        "event_id": event_id,
        "target_url": target_url,
        "payload": body_str,
        "payload_is_json": "1" if is_json else "0",
        "headers": _to_json_str(headers),
        "attempt": "0",
        "max_attempts": str(int(max_attempts)),
        "backoff_base": str(b_base),
        "backoff_factor": str(b_factor),
        "backoff_jitter": str(b_jitter),
        "backoff_max": str(b_max),
        "created_at": str(_now()),
    }
    if secret:
        job_data["secret"] = secret

    pipe = r.pipeline(True)
    # Store job
    pipe.hset(_job_key(job_id), mapping=job_data)
    pipe.expire(_job_key(job_id), settings.job_retention_seconds)
    # Set initial status
    status = {
        "event_id": event_id,
        "state": "queued",
        "attempt_count": "0",
        "last_attempt_at": "",
        "last_response_code": "",
        "last_error": "",
        "created_at": str(_now()),
    }
    pipe.hset(_status_key(event_id), mapping=status)
    pipe.expire(_status_key(event_id), settings.status_retention_seconds)
    # Push to queue now
    pipe.zadd(QUEUE_KEY, {job_id: _now()})
    pipe.execute()

    return {
        "event_id": event_id,
        "job_id": job_id,
    }


@app.route("/webhooks/send", methods=["POST"])
def send_webhook():
    data = request.get_json(silent=True) or {}
    target_url = data.get("target_url")
    payload = data.get("payload")
    headers = data.get("headers") or {}
    event_id = data.get("event_id")
    max_attempts = data.get("max_attempts")
    backoff = data.get("backoff")
    secret = data.get("secret")

    if not target_url:
        return jsonify({"error": "target_url is required"}), 400
    if payload is None:
        return jsonify({"error": "payload is required"}), 400

    result = enqueue_webhook(
        target_url=target_url,
        payload=payload,
        headers=headers,
        event_id=event_id,
        max_attempts=max_attempts,
        backoff=backoff,
        secret=secret,
    )

    res = {
        **result,
        "status_url": f"/webhooks/status/{result['event_id']}",
    }
    return jsonify(res), 202


@app.route("/webhooks/status/<event_id>", methods=["GET"])
def webhook_status(event_id: str):
    r = get_redis()
    status = r.hgetall(_status_key(event_id))
    if not status:
        return jsonify({"error": "not found"}), 404
    history = r.lrange(_history_key(event_id), 0, 50)
    history = [json.loads(x) for x in history]
    status["attempt_count"] = int(status.get("attempt_count", 0))
    return jsonify({"status": status, "history": history})


@app.route("/healthz", methods=["GET"])
def healthz():
    try:
        r = get_redis()
        r.ping()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



def create_app():
    return app
