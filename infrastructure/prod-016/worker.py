import json
import time
import random
import hmac
from hashlib import sha256
from typing import Optional, Dict, Any

import requests

from config import settings
from redis_client import get_redis

QUEUE_KEY = settings.queue_key


def _now() -> float:
    return time.time()


def _job_key(job_id: str) -> str:
    return f"webhook:job:{job_id}"


def _status_key(event_id: str) -> str:
    return f"webhook:status:{event_id}"


def _history_key(event_id: str) -> str:
    return f"webhook:history:{event_id}"


POP_DUE_JOB_LUA = """
local qkey = KEYS[1]
local now = tonumber(ARGV[1])
local res = redis.call('ZRANGEBYSCORE', qkey, '-inf', now, 'LIMIT', 0, 1)
if #res == 0 then return nil end
local job_id = res[1]
redis.call('ZREM', qkey, job_id)
return job_id
"""


def pop_due_job_id() -> Optional[str]:
    r = get_redis()
    try:
        job_id = r.eval(POP_DUE_JOB_LUA, 1, QUEUE_KEY, _now())
        return job_id
    except Exception:
        return None


def hgetall_job(job_id: str) -> Dict[str, str]:
    r = get_redis()
    return r.hgetall(_job_key(job_id))


def update_status(event_id: str, fields: Dict[str, Any]):
    r = get_redis()
    str_fields = {k: (str(v) if v is not None else "") for k, v in fields.items()}
    pipe = r.pipeline(True)
    pipe.hset(_status_key(event_id), mapping=str_fields)
    pipe.expire(_status_key(event_id), settings.status_retention_seconds)
    pipe.execute()


def push_history(event_id: str, record: Dict[str, Any]):
    r = get_redis()
    pipe = r.pipeline(True)
    pipe.lpush(_history_key(event_id), json.dumps(record, separators=(",", ":")))
    pipe.ltrim(_history_key(event_id), 0, 99)
    pipe.expire(_history_key(event_id), settings.status_retention_seconds)
    pipe.execute()


def schedule_retry(job_id: str, delay: float, new_attempt: int):
    r = get_redis()
    pipe = r.pipeline(True)
    pipe.hset(_job_key(job_id), mapping={"attempt": str(new_attempt)})
    pipe.zadd(QUEUE_KEY, {job_id: _now() + delay})
    pipe.execute()


def finalize_job(job_id: str):
    r = get_redis()
    r.expire(_job_key(job_id), settings.job_retention_seconds)


def compute_backoff(base: float, factor: float, jitter: float, max_b: float, attempt_index: int) -> float:
    # attempt_index starts at 1 for first retry
    delay = base * (factor ** max(0, attempt_index - 1))
    if jitter > 0:
        delay = delay + random.uniform(0, jitter)
    return min(delay, max_b)


def sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()


def notify_failure(payload: Dict[str, Any]):
    url = settings.failure_notify_url
    if not url:
        return
    try:
        headers = {"Content-Type": "application/json", "User-Agent": settings.user_agent}
        requests.post(url, data=json.dumps(payload), headers=headers, timeout=5)
    except Exception:
        # Avoid raising inside worker
        pass


def deliver(job_id: str, job: Dict[str, str]):
    event_id = job.get("event_id")
    target_url = job.get("target_url")
    attempt = int(job.get("attempt", "0"))
    max_attempts = int(job.get("max_attempts", str(settings.default_max_attempts)))

    backoff_base = float(job.get("backoff_base", str(settings.backoff_base)))
    backoff_factor = float(job.get("backoff_factor", str(settings.backoff_factor)))
    backoff_jitter = float(job.get("backoff_jitter", str(settings.backoff_jitter)))
    backoff_max = float(job.get("backoff_max", str(settings.backoff_max)))

    body_str = job.get("payload", "")
    is_json = job.get("payload_is_json", "0") == "1"

    headers = {}
    try:
        headers = json.loads(job.get("headers", "{}"))
    except Exception:
        headers = {}

    # Prepare request
    body_bytes = body_str.encode("utf-8")
    if "Content-Type" not in {k.title(): v for k, v in headers.items()}:
        headers.setdefault("Content-Type", "application/json" if is_json else "text/plain; charset=utf-8")
    headers.setdefault("User-Agent", settings.user_agent)

    secret = job.get("secret")
    if secret:
        signature = sign_body(secret, body_bytes)
        headers.setdefault("X-Signature-SHA256", signature)

    started_at = _now()
    status_code = None
    error_msg = ""
    duration_ms = None

    try:
        resp = requests.post(target_url, data=body_bytes, headers=headers, timeout=settings.request_timeout)
        status_code = resp.status_code
        ok = 200 <= resp.status_code < 300
        duration_ms = int((_now() - started_at) * 1000)
    except Exception as e:
        ok = False
        error_msg = str(e)
        duration_ms = int((_now() - started_at) * 1000)

    # Record attempt
    attempt_no = attempt + 1
    history_record = {
        "ts": started_at,
        "attempt": attempt_no,
        "url": target_url,
        "status_code": status_code if status_code is not None else "",
        "error": error_msg,
        "duration_ms": duration_ms,
    }
    push_history(event_id, history_record)

    # Update status
    st_fields = {
        "state": "delivered" if ok else "retrying",
        "attempt_count": attempt_no,
        "last_attempt_at": started_at,
        "last_response_code": status_code if status_code is not None else "",
        "last_error": error_msg,
    }

    if ok:
        update_status(event_id, st_fields)
        finalize_job(job_id)
        return

    # Not ok: decide retry or fail
    if attempt_no >= max_attempts:
        st_fields["state"] = "failed"
        update_status(event_id, st_fields)
        finalize_job(job_id)
        # Notify failure
        notify_failure({
            "event_id": event_id,
            "target_url": target_url,
            "attempts": attempt_no,
            "last_response_code": status_code,
            "last_error": error_msg,
            "failed_at": started_at,
        })
        return

    # Schedule retry
    delay = compute_backoff(backoff_base, backoff_factor, backoff_jitter, backoff_max, attempt_no)
    update_status(event_id, st_fields)
    schedule_retry(job_id, delay, attempt_no)


def worker_loop():
    print("[worker] starting loop, queue=", QUEUE_KEY)
    while True:
        try:
            job_id = pop_due_job_id()
            if not job_id:
                time.sleep(settings.poll_interval)
                continue
            job = hgetall_job(job_id)
            if not job:
                continue
            deliver(job_id, job)
        except KeyboardInterrupt:
            print("[worker] stopping")
            break
        except Exception as e:
            # Log and continue
            print(f"[worker] error: {e}")
            time.sleep(0.5)


if __name__ == "__main__":
    worker_loop()

