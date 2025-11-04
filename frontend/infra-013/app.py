import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import atexit
import hashlib
import json
import time
import uuid
from typing import Any, Dict

from flask import Flask, Response, g, jsonify, request

from config import Config
from processor.events import Event, EventProcessor
from retry.manager import RetryManager
from utils.id_cache import TTLCache
from utils.logging import configure_logging, get_logger
from utils.signature import verify_signature


configure_logging(Config.LOG_LEVEL)
logger = get_logger("webhook")

app = Flask(__name__)

# Idempotency cache for received event IDs
_event_cache = TTLCache(maxsize=Config.IDEMPOTENCY_MAXSIZE, ttl_seconds=Config.IDEMPOTENCY_TTL_SECONDS)

# Processor and retry manager
processor = EventProcessor(logger)
retry_manager = RetryManager(
    processor=processor,
    logger=logger,
    max_retries=Config.MAX_RETRIES,
    backoff_base=Config.BACKOFF_BASE_SECONDS,
    backoff_factor=Config.BACKOFF_FACTOR,
    backoff_max=Config.BACKOFF_MAX_SECONDS,
    jitter=Config.JITTER_SECONDS,
)
retry_manager.start()
atexit.register(retry_manager.stop)


@app.before_request
def _before_request() -> None:
    g.request_start = time.time()
    # Honor upstream request ID if present
    req_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    g.request_id = req_id


@app.after_request
def _after_request(resp: Response) -> Response:
    duration_ms = int((time.time() - g.get("request_start", time.time())) * 1000)
    resp.headers["X-Request-Id"] = g.get("request_id", "")
    # Access log
    extra = {
        "request_id": g.get("request_id"),
        "remote_addr": request.remote_addr,
        "method": request.method,
        "path": request.path,
        "status_code": resp.status_code,
    }
    logger.info(f"{request.method} {request.path} -> {resp.status_code} {duration_ms}ms", extra=extra)
    return resp


@app.route("/health", methods=["GET"]) 
def health() -> Response:
    return jsonify({"status": "ok"})


@app.route("/webhook", methods=["POST"]) 
def webhook() -> Response:
    raw_body = request.get_data(cache=False)

    err = verify_signature(
        headers=request.headers,
        body=raw_body,
        secret=Config.WEBHOOK_SECRET,
        tolerance_seconds=Config.TIMESTAMP_TOLERANCE_SECONDS,
    )
    if err is not None:
        logger.warning("signature verification failed", extra={"request_id": g.get("request_id")})
        return jsonify({"error": err}), 401

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "invalid json"}), 400

    event_type = str(data.get("type")) if data.get("type") else None
    if not event_type:
        return jsonify({"error": "missing event type"}), 400

    event_id = data.get("id")
    if not event_id:
        # derive a deterministic ID from payload to support idempotency when no ID is provided
        event_id = hashlib.sha256(raw_body).hexdigest()

    # Idempotency: drop duplicates
    if not _event_cache.add_if_new(event_id):
        logger.info("duplicate event ignored", extra={"event_id": event_id, "event_type": event_type})
        return jsonify({"status": "duplicate"}), 200

    evt = Event(id=event_id, type=event_type, payload=data, received_at=time.time())
    retry_manager.enqueue_event(evt)

    return jsonify({"status": "accepted", "id": event_id, "type": event_type}), 202


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT)



def create_app():
    return app
