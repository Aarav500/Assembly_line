import os
import random
import time
from flask import Flask, jsonify

from common.tracing import setup_tracing
from opentelemetry import trace

app = Flask(__name__)
tracer = setup_tracing("service-b", flask_app=app)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/process")
def process():
    # Flask instrumentation will create a span for this request; we add a child span for the work
    with tracer.start_as_current_span("service-b.work") as span:
        span.set_attribute("component", "service-b")
        # Simulate variable processing time
        delay = random.uniform(0.05, 0.3)
        time.sleep(delay)
        span.set_attribute("work.delay_ms", int(delay * 1000))
        return jsonify({"status": "processed", "delay_ms": int(delay * 1000)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5001)))

