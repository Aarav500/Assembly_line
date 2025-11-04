import hashlib
import time
from typing import Optional

from flask import Request, Response, g, request


def request_timer_before():
    g._start_time = time.perf_counter()


def _compute_etag(resp: Response, max_len: int = 1024 * 1024) -> Optional[str]:
    # Skip streaming or very large
    if resp.direct_passthrough:
        return None
    data = resp.get_data()
    if not data or len(data) > max_len:
        return None
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def add_common_headers(resp: Response) -> Response:
    # Default sensible caching if none set
    if "Cache-Control" not in resp.headers:
        resp.headers["Cache-Control"] = (
            "public, max-age=30, s-maxage=300, stale-while-revalidate=30, stale-if-error=86400"
        )
    # CDN hints
    if "Surrogate-Control" not in resp.headers:
        resp.headers["Surrogate-Control"] = "max-age=300, stale-while-revalidate=30, stale-if-error=86400"

    # Early resource hints (safe defaults)
    if "Link" not in resp.headers:
        hints = [
            "<https://fonts.gstatic.com>; rel=preconnect; crossorigin",
        ]
        resp.headers["Link"] = ", ".join(hints)

    # Security and variability
    vary_values = [v.strip() for v in (resp.headers.get("Vary", "") + ", Accept-Encoding").split(",") if v.strip()]
    resp.headers["Vary"] = ", ".join(sorted(set(vary_values)))

    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Timing-Allow-Origin", "*")

    # ETag if appropriate and not set
    if not resp.get_etag()[0]:
        etag = _compute_etag(resp)
        if etag:
            resp.set_etag(etag, weak=True)
            if request.if_none_match and etag in request.if_none_match:
                resp.status_code = 304
                resp.set_data(b"")
                # remove content-specific headers
                for h in ["Content-Length", "Content-MD5"]:
                    resp.headers.pop(h, None)
    return resp


def request_timer_after(resp: Response) -> Response:
    try:
        dur_ms = (time.perf_counter() - getattr(g, "_start_time", time.perf_counter())) * 1000.0
        existing = resp.headers.get("Server-Timing")
        timing = f"app;dur={dur_ms:.1f}"
        resp.headers["Server-Timing"] = f"{existing}, {timing}" if existing else timing
    except Exception:
        pass
    return resp

