import json
import os
import random
import time

import requests
from redis import Redis

from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.propagate import extract

from common.tracing import setup_tracing

SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://localhost:5001")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = os.getenv("QUEUE_NAME", "jobs")

tracer = setup_tracing("job-worker")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


def process_job(job):
    # Extract remote parent context from job trace carrier
    carrier = job.get("trace", {}) or {}
    ctx = extract(carrier)
    token = attach(ctx)

    try:
        with tracer.start_as_current_span("job.process") as span:
            span.set_attribute("component", "job-worker")
            span.set_attribute("job.id", job.get("job_id", "unknown"))
            payload = job.get("payload", {})
            span.set_attribute("job.action", payload.get("action", "unknown"))

            # Simulate some work
            compute_ms = random.randint(100, 400)
            time.sleep(compute_ms / 1000.0)
            span.set_attribute("job.compute_ms", compute_ms)

            # Optionally call service-b as part of job processing to demonstrate cross-service linkage from async
            try:
                r = requests.get(f"{SERVICE_B_URL}/process", timeout=5)
                span.set_attribute("service_b.status_code", r.status_code)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("service_b.error", True)
    finally:
        detach(token)


def main():
    print("Worker started; waiting for jobs on queue:", QUEUE_NAME, flush=True)
    while True:
        try:
            # Use BRPOP to block until a job is available
            _, raw = redis_client.brpop(QUEUE_NAME, timeout=0)
            job = json.loads(raw)
            process_job(job)
        except KeyboardInterrupt:
            print("Worker shutting down...")
            break
        except Exception as e:
            # Do not crash the worker on malformed messages
            print("Error processing job:", repr(e), flush=True)
            time.sleep(0.5)


if __name__ == "__main__":
    main()

