import os

from flask import Flask, jsonify, request

from common import (
    attach_request_hooks,
    setup_logging,
    get_logger,
    get_request_id,
    get_trace_id,
    get_span_id,
)

SERVICE_NAME = os.getenv("SERVICE_NAME", "service-b")

setup_logging(service_name=SERVICE_NAME)
logger = get_logger(__name__)

app = Flask(__name__)
attach_request_hooks(app)


@app.route("/echo", methods=["GET"])  # echoes message and shows observed headers
def echo():
    msg = request.args.get("msg", "hello")
    logger.info("echo", extra={"message": msg})

    observed_headers = {
        "x-request-id": request.headers.get("X-Request-ID"),
        "traceparent": request.headers.get("traceparent") or request.headers.get("Traceparent"),
    }

    return jsonify(
        {
            "service": SERVICE_NAME,
            "received_msg": msg,
            "request_id": get_request_id(),
            "trace_id": get_trace_id(),
            "span_id": get_span_id(),
            "observed_headers": observed_headers,
        }
    )


@app.route("/ping", methods=["GET"])  # health + tracing check
def ping():
    logger.info("ping")
    return jsonify(
        {
            "service": SERVICE_NAME,
            "message": "pong",
            "request_id": get_request_id(),
            "trace_id": get_trace_id(),
            "span_id": get_span_id(),
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5002"))
    app.run(host="0.0.0.0", port=port)

