import logging
from typing import Dict, Optional

import requests

from .tracing import (
    get_request_id,
    get_trace_id,
    generate_trace_id,
    generate_span_id,
    build_traceparent,
)

logger = logging.getLogger(__name__)


class TracedSession(requests.Session):
    def __init__(self, propagate_headers: Optional[Dict[str, str]] = None, default_timeout: Optional[float] = 5.0):
        super().__init__()
        self.default_timeout = default_timeout
        # Static headers to copy from incoming request if present (key mapping: incoming -> outgoing)
        self.propagate_headers = propagate_headers or {}

    def request(self, method, url, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})

        # Correlation: X-Request-ID
        req_id = get_request_id()
        if req_id and "X-Request-ID" not in headers and "x-request-id" not in {k.lower() for k in headers}:
            headers["X-Request-ID"] = req_id

        # Trace Context: build child span traceparent
        trace_id = get_trace_id() or generate_trace_id()
        child_span_id = generate_span_id()
        headers["Traceparent"] = build_traceparent(trace_id, child_span_id)

        # Apply static propagated headers if they are present
        for incoming_key, outgoing_key in self.propagate_headers.items():
            try:
                from flask import has_request_context, request as flask_request

                if has_request_context():
                    val = flask_request.headers.get(incoming_key)
                    if val and outgoing_key not in headers:
                        headers[outgoing_key] = val
            except Exception:
                pass

        # Timeout handling
        if "timeout" not in kwargs and self.default_timeout is not None:
            kwargs["timeout"] = self.default_timeout

        kwargs["headers"] = headers

        logger.debug(
            "Outgoing request",
            extra={
                "method": method,
                "path": url,
            },
        )
        resp = super().request(method, url, **kwargs)
        logger.debug(
            "Received response",
            extra={
                "method": method,
                "path": url,
            },
        )
        return resp


_default_session: Optional[TracedSession] = None


def get_default_session() -> TracedSession:
    global _default_session
    if _default_session is None:
        _default_session = TracedSession()
    return _default_session

