from opentelemetry import trace


def current_trace_id_hex() -> str:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or not ctx.trace_id:
        return ""
    return f"{ctx.trace_id:032x}"

