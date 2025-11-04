import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import random
import logging
from threading import Thread
from flask import Flask, request, jsonify, g
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from metrics import (
    REQUEST_LATENCY,
    REQUEST_COUNT,
    IN_FLIGHT,
    ORDERS_CREATED,
    ORDER_VALUE,
    ORDER_PROCESSING_SECONDS,
    ACTIVE_USERS,
    INVENTORY_LEVEL,
    QUEUE_DEPTH,
    REVENUE_TOTAL,
    SERVICE_INFO,
)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("metrics-exporter")

app = Flask(__name__)

APP_NAME = os.environ.get("APP_NAME", "metrics-exporter-prometheus-custom-business-metrics")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
SERVICE_VERSION = os.environ.get("SERVICE_VERSION", "0.1.0")

# Set static service metadata
SERVICE_INFO.info({
    "name": APP_NAME,
    "environment": ENVIRONMENT,
    "version": SERVICE_VERSION,
})


def _endpoint_label() -> str:
    try:
        if request.url_rule and request.url_rule.rule:
            return request.url_rule.rule
    except Exception:
        pass
    return "unknown"


@app.before_request
def before_request():
    g._start_time = time.perf_counter()
    g._in_flight_inc = True
    IN_FLIGHT.inc()


@app.after_request
def after_request(response):
    try:
        elapsed = time.perf_counter() - getattr(g, "_start_time", time.perf_counter())
        method = request.method
        endpoint = _endpoint_label()
        status_code = str(response.status_code)

        REQUEST_LATENCY.labels(method=method, endpoint=endpoint, status_code=status_code).observe(elapsed)
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    finally:
        if getattr(g, "_in_flight_inc", False):
            IN_FLIGHT.dec()
            g._in_flight_inc = False
    return response


@app.teardown_request
def teardown_request(exception):
    if getattr(g, "_in_flight_inc", False):
        # Ensure gauge decremented on error paths
        IN_FLIGHT.dec()
        g._in_flight_inc = False


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "service": APP_NAME, "env": ENVIRONMENT, "version": SERVICE_VERSION}), 200


@app.route("/readyz")
def readyz():
    # Add readiness checks as needed
    return jsonify({"ready": True}), 200


@app.route("/order", methods=["POST"])  # Simulate or ingest order events
def create_order():
    payload = request.get_json(silent=True) or {}

    amount = float(payload.get("amount", round(random.uniform(5.0, 250.0), 2)))
    currency = str(payload.get("currency", "USD"))
    payment_method = str(payload.get("payment_method", random.choice(["card", "paypal", "bank_transfer"])) )
    simulate_failure = bool(payload.get("simulate_failure", False))
    status = "failed" if simulate_failure else "success"

    # Optional order processing time (seconds)
    processing_time = payload.get("processing_time")
    if processing_time is None:
        # Log-normal-ish distribution around ~300ms
        processing_time = max(0.01, min(3.0, random.lognormvariate(-1.2, 0.6)))
    try:
        processing_time = float(processing_time)
    except Exception:
        processing_time = 0.1

    # Bound the sleep to avoid long blocking
    time.sleep(min(processing_time, 1.0))

    # Update business metrics
    ORDERS_CREATED.labels(status=status, currency=currency, payment_method=payment_method).inc()
    ORDER_PROCESSING_SECONDS.labels(status=status).observe(processing_time)

    if status == "success":
        ORDER_VALUE.observe(amount)
        REVENUE_TOTAL.labels(currency=currency).inc(amount)

    # Optional inventory interaction
    product_id = payload.get("product_id")
    quantity = payload.get("quantity")
    if product_id is not None and quantity is not None:
        try:
            quantity = float(quantity)
            # Assume success decreases inventory; failure leaves unchanged
            if status == "success":
                # If no prior value, default to 100 then decrement
                current = None
                # NOTE: prometheus_client does not support reading current gauge value directly.
                # We'll simulate with a simple convention: if client sends absolute level, we set it.
                # Else we decrement from an assumed base.
                if payload.get("absolute_level") is not None:
                    INVENTORY_LEVEL.labels(product_id=str(product_id)).set(float(payload["absolute_level"]))
                else:
                    # Decrement from an implicit baseline by simply setting a new level if not previously set.
                    # As prometheus_client doesn't expose current gauge state, in real usage you'd track in storage.
                    # Here, we just emit a set to a pseudo-level for demonstration.
                    pseudo_level = max(0.0, 100.0 - quantity)
                    INVENTORY_LEVEL.labels(product_id=str(product_id)).set(pseudo_level)
        except Exception:
            pass

    # Optionally simulate queue depth changes
    QUEUE_DEPTH.labels(queue_name="orders").set(random.randint(0, 50))

    return jsonify({
        "status": status,
        "amount": amount,
        "currency": currency,
        "payment_method": payment_method,
        "processing_time": processing_time,
    }), (200 if status == "success" else 500)


@app.route("/users/active", methods=["POST"])  # Set active users gauge
def set_active_users():
    payload = request.get_json(silent=True) or {}
    try:
        value = float(payload.get("value"))
    except Exception:
        return jsonify({"error": "value must be a number"}), 400
    ACTIVE_USERS.set(max(0.0, value))
    return jsonify({"active_users": value}), 200


@app.route("/queue-depth", methods=["POST"])  # Set depth for a named queue
def set_queue_depth():
    payload = request.get_json(silent=True) or {}
    queue_name = str(payload.get("queue_name", "default"))
    try:
        depth = float(payload.get("depth"))
    except Exception:
        return jsonify({"error": "depth must be a number"}), 400
    QUEUE_DEPTH.labels(queue_name=queue_name).set(max(0.0, depth))
    return jsonify({"queue_name": queue_name, "depth": depth}), 200


def _simulation_loop():
    logger.info("Starting metrics simulation loop")
    # Initialize some labels
    QUEUE_DEPTH.labels(queue_name="orders").set(0)

    while True:
        try:
            # Simulate active users fluctuating between 5 and 200
            ACTIVE_USERS.set(random.randint(5, 200))

            # Simulate queue depth for orders
            QUEUE_DEPTH.labels(queue_name="orders").set(max(0, int(random.gauss(10, 5))))

            # Emit occasional revenue increments through synthetic orders
            if random.random() < 0.3:
                amt = round(random.uniform(10, 150), 2)
                currency = "USD"
                ORDERS_CREATED.labels(status="success", currency=currency, payment_method="card").inc()
                ORDER_VALUE.observe(amt)
                REVENUE_TOTAL.labels(currency=currency).inc(amt)
                ORDER_PROCESSING_SECONDS.labels(status="success").observe(random.uniform(0.05, 0.8))
        except Exception as e:
            logger.exception("Error in simulation loop: %s", e)
        time.sleep(5.0)


def _maybe_start_simulator():
    enable = os.environ.get("ENABLE_SIMULATOR", "1").lower() not in ("0", "false", "no")
    if enable:
        t = Thread(target=_simulation_loop, daemon=True)
        t.start()
        logger.info("Simulator enabled")
    else:
        logger.info("Simulator disabled via ENABLE_SIMULATOR")


_maybe_start_simulator()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app
