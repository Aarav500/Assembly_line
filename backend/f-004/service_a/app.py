import json
import os
import time
from uuid import uuid4

import requests
from flask import Flask, jsonify
from redis import Redis

from opentelemetry import trace
from opentelemetry.propagate import inject

from common.tracing import setup_tracing
from common.utils import current_trace_id_hex

app = Flask(__name__)
tracer = setup_tracing("service-a", flask_app=app)

SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://localhost:5001")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = os.getenv("QUEUE_NAME", "jobs")

redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/do-work")
def do_work():
    with tracer.start_as_current_span("do_work") as span:
        span.set_attribute("component", "service-a")
        trace_id = current_trace_id_hex()

        # Call downstream service B (HTTP) - headers auto-injected by requests instrumentation
        service_b_resp = requests.get(f"{SERVICE_B_URL}/process", timeout=5)
        span.set_attribute("service_b.status_code", service_b_resp.status_code)

        # Enqueue an async job with trace context injected
        carrier = {}
        inject(carrier)
        job = {
            "job_id": str(uuid4()),
            "trace": carrier,
            "payload": {
                "action": "heavy_compute",
                "submitted_at": time.time(),
            },
        }
        redis_client.lpush(QUEUE_NAME, json.dumps(job))
        span.add_event("job_enqueued", attributes={"job.id": job["job_id"], "queue": QUEUE_NAME})

        return jsonify({
            "message": "Work initiated: called service-b and enqueued job",
            "service_b": service_b_resp.json(),
            "job_id": job["job_id"],
            "trace_id": trace_id,
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

