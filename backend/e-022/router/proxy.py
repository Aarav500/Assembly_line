import hashlib
from typing import Dict
import requests
from flask import request, Response


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def filter_headers(original_headers: Dict[str, str]) -> Dict[str, str]:
    return {
        k: v
        for k, v in original_headers.items()
        if k.lower() not in HOP_BY_HOP_HEADERS and k.lower() != "host"
    }


class ReverseProxy:
    def __init__(self, orchestrator, *, timeout: float = 10.0, sticky_sessions: bool = True) -> None:
        self.orchestrator = orchestrator
        self.timeout = timeout
        self.sticky_sessions = sticky_sessions

    def _session_hash(self) -> int:
        # Use a provided header/cookie to ensure sticky routing during canary.
        # Priority: X-Session-Key header, then Cookie "session_id", then X-Forwarded-For
        key = (
            request.headers.get("X-Session-Key")
            or request.cookies.get("session_id")
            or request.headers.get("X-Forwarded-For")
            or request.remote_addr
            or ""
        )
        if not key:
            return None
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return int(h[:8], 16)  # 32-bit int from hash

    def forward(self):
        # Decide upstream
        sess_hash = self._session_hash() if self.sticky_sessions else None
        color, upstream_base = self.orchestrator.choose(session_hash=sess_hash)

        # Construct target URL
        # Preserve path and query string
        target_url = upstream_base.rstrip("/") + request.path
        params = request.args.to_dict(flat=False)
        data = request.get_data()
        headers = filter_headers(dict(request.headers))

        # Proxy request
        try:
            r = requests.request(
                method=request.method,
                url=target_url,
                params=params,
                data=data if request.method not in ("GET", "HEAD") else None,
                headers=headers,
                cookies=request.cookies,
                allow_redirects=False,
                timeout=self.timeout,
                stream=False,
            )
        except requests.RequestException as e:
            # Upstream error; return 502
            return Response(str(e), status=502)

        # Build Flask response
        resp_headers = [(k, v) for k, v in r.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS]
        # Add routing metadata
        resp_headers.append(("X-Routed-To", color))
        resp_headers.append(("X-Upstream-URL", upstream_base))

        return Response(r.content, status=r.status_code, headers=resp_headers)

