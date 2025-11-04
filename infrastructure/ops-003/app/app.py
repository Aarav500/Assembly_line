import os
import random
import threading
import time
from typing import Tuple

from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_TEAM = os.getenv("APP_TEAM", "core")
_error_rate_lock = threading.Lock()
_error_rate = float(os.getenv("ERROR_RATE", "0.02"))

REQ_COUNTER = Counter(
    "app_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
ERR_COUNTER = Counter(
    "app_http_request_errors_total",
    "Total HTTP request errors",
    ["method", "endpoint", "status"],
)
LATENCY_HIST = Histogram(
    "app_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"],
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
)
BG_JOBS = Gauge(
    "app_background_jobs",
    "Number of background jobs queued",
)
TEAM_INFO = Gauge(
    "app_team_info",
    "Static label to expose team ownership",
    ["team"],
)
TEAM_INFO.labels(team=APP_TEAM).set(1)


def _current_error_rate() -> float:
    with _error_rate_lock:
        return _error_rate


def _set_error_rate(val: float) -> None:
    global _error_rate
    with _error_rate_lock:
        _error_rate = max(0.0, min(1.0, val))


def simulate_work(endpoint: str, min_ms: int = 20, max_ms: int = 800) -> Tuple[str, int]:
    start = time.time()
    # Simulate variable latency
    delay_ms = random.randint(min_ms, max_ms)
    # Occasionally heavy tail
    if random.random() < 0.05:
        delay_ms += random.randint(200, 800)
    time.sleep(delay_ms / 1000.0)

    status = 200
    if request.args.get("fail") == "1" or random.random() < _current_error_rate():
        status = 500

    LATENCY_HIST.labels(endpoint=endpoint).observe(time.time() - start)

    method = request.method
    REQ_COUNTER.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    if status >= 400:
        ERR_COUNTER.labels(method=method, endpoint=endpoint, status=str(status)).inc()

    payload = {
        "ok": status == 200,
        "endpoint": endpoint,
        "status": status,
        "team": APP_TEAM,
        "delay_ms": delay_ms,
        "error_rate": _current_error_rate(),
    }
    return jsonify(payload), status


@app.route("/")
def index():
    return simulate_work("root")


@app.route("/work")
def work():
    return simulate_work("work")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "team": APP_TEAM}), 200


@app.route("/set_error_rate")
def set_error_rate():
    try:
        rate = float(request.args.get("rate", ""))
    except ValueError:
        return jsonify({"error": "invalid rate"}), 400
    _set_error_rate(rate)
    return jsonify({"error_rate": _current_error_rate()}), 200


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


def _bg_job_simulator():
    while True:
        BG_JOBS.set(max(0, int(random.gauss(mu=5, sigma=2))))
        time.sleep(5)


if __name__ == "__main__":
    threading.Thread(target=_bg_job_simulator, daemon=True).start()
    app.run(host="0.0.0.0", port=APP_PORT)

