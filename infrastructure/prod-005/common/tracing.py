import uuid
import secrets
from contextvars import ContextVar
from typing import Optional, Tuple

from flask import g, request


# Context variables for correlation
_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_span_id_var: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


def generate_request_id() -> str:
    return str(uuid.uuid4())


def generate_trace_id() -> str:
    # 16 bytes -> 32 hex chars
    return secrets.token_hex(16)


def generate_span_id() -> str:
    # 8 bytes -> 16 hex chars
    return secrets.token_hex(8)


def build_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    # W3C Trace Context: version(2)-trace-id(32)-parent-id(16)-flags(2)
    # version '00', flags '01' for sampled, '00' for not sampled
    flags = "01" if sampled else "00"
    return f"00-{trace_id}-{span_id}-{flags}"


def parse_traceparent(header: str) -> Optional[Tuple[str, str, str]]:
    # returns (trace_id, parent_span_id, flags)
    try:
        parts = header.strip().split("-")
        if len(parts) < 4:
            return None
        version, trace_id, parent_id, flags = parts[:4]
        if len(version) != 2:
            return None
        if len(trace_id) != 32:
            return None
        if len(parent_id) != 16:
            return None
        if len(flags) != 2:
            return None
        int(trace_id, 16)
        int(parent_id, 16)
        int(flags, 16)
        return trace_id.lower(), parent_id.lower(), flags.lower()
    except Exception:
        return None


def set_request_context(request_id: str, trace_id: str, span_id: str) -> None:
    _request_id_var.set(request_id)
    _trace_id_var.set(trace_id)
    _span_id_var.set(span_id)
    g.request_id = request_id
    g.trace_id = trace_id
    g.span_id = span_id


def clear_request_context() -> None:
    _request_id_var.set(None)
    _trace_id_var.set(None)
    _span_id_var.set(None)
    # g may not exist during teardown in some cases; guard it
    for attr in ("request_id", "trace_id", "span_id"):
        try:
            if hasattr(g, attr):
                delattr(g, attr)
        except Exception:
            pass


def get_request_id(default: Optional[str] = None) -> Optional[str]:
    return _request_id_var.get() or default


def get_trace_id(default: Optional[str] = None) -> Optional[str]:
    return _trace_id_var.get() or default


def get_span_id(default: Optional[str] = None) -> Optional[str]:
    return _span_id_var.get() or default


_INBOUND_REQ_ID_HEADER_CANDIDATES = [
    "X-Request-ID",
    "X-Request-Id",
    "X-Correlation-ID",
    "X-Correlation-Id",
]


def _extract_incoming_request_id() -> Optional[str]:
    for key in _INBOUND_REQ_ID_HEADER_CANDIDATES:
        val = request.headers.get(key)
        if val:
            return val.strip()
    return None


def attach_request_hooks(app):
    @app.before_request
    def _before_request():
        # Request ID
        incoming_req_id = _extract_incoming_request_id()
        request_id = incoming_req_id or generate_request_id()

        # Traceparent processing
        incoming_tp = request.headers.get("traceparent") or request.headers.get("Traceparent")
        parsed = parse_traceparent(incoming_tp) if incoming_tp else None
        if parsed:
            trace_id, _parent_span_id, _flags = parsed
        else:
            trace_id = generate_trace_id()
        # Current span id for this request
        span_id = generate_span_id()

        set_request_context(request_id=request_id, trace_id=trace_id, span_id=span_id)

    @app.after_request
    def _after_request(response):
        rid = get_request_id()
        tid = get_trace_id()
        sid = get_span_id()
        if rid:
            response.headers["X-Request-ID"] = rid
        if tid and sid:
            response.headers["Traceparent"] = build_traceparent(tid, sid)
        return response

    @app.teardown_request
    def _teardown_request(_exc):
        clear_request_context()

    return app

