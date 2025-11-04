import os
import logging
from urllib.parse import urlencode

from flask import Flask, jsonify, request

from common import (
    attach_request_hooks,
    setup_logging,
    get_logger,
    get_request_id,
    get_trace_id,
    get_span_id,
)
from common.http_client import get_default_session


SERVICE_NAME = os.getenv("SERVICE_NAME", "service-a")

setup_logging(service_name=SERVICE_NAME)
logger = get_logger(__name__)

app = Flask(__name__)
attach_request_hooks(app)
http = get_default_session()


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


@app.route("/call-b", methods=["GET"])  # call service-b to demonstrate propagation
def call_b():
    target = os.getenv("SERVICE_B_URL", "http://localhost:5002/echo")
    msg = request.args.get("msg", "hello-from-a")
    url = f"{target}?" + urlencode({"msg": msg})

    logger.info("calling service-b", extra={"path": url})
    r = http.get(url)
    r.raise_for_status()

    payload = r.json()
    return jsonify(
        {
            "service": SERVICE_NAME,
            "request_id": get_request_id(),
            "trace_id": get_trace_id(),
            "span_id": get_span_id(),
            "called": payload,
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port)

