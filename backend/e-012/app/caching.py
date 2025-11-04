import hashlib
import time
from typing import Iterable, List, Optional
from flask import current_app, Response


def _compute_etag(payload: bytes, release_sha: str) -> str:
    h = hashlib.sha1()
    h.update(payload or b"")
    h.update((release_sha or "").encode("utf-8"))
    return 'W/"' + h.hexdigest() + '"'


def _merge_header(resp: Response, name: str, value: str, sep: str = ", ") -> None:
    if not value:
        return
    existing = resp.headers.get(name)
    if existing:
        # Avoid duplicates
        parts = [p.strip() for p in (existing.split(sep) + value.split(sep)) if p.strip()]
        seen = []
        merged = []
        for p in parts:
            if p not in seen:
                seen.append(p)
                merged.append(p)
        resp.headers[name] = sep.join(merged)
    else:
        resp.headers[name] = value


def set_cache_headers(
    resp: Response,
    ttl: Optional[int] = None,
    surrogate_ttl: Optional[int] = None,
    keys: Optional[Iterable[str]] = None,
    enable_etag: Optional[bool] = None,
) -> Response:
    cfg = current_app.config
    ttl = cfg.get("DEFAULT_TTL", 60) if ttl is None else ttl
    surrogate_ttl = cfg.get("SURROGATE_TTL", 300) if surrogate_ttl is None else surrogate_ttl

    # Cache-Control for browsers and shared caches
    _merge_header(resp, "Cache-Control", f"public, max-age={int(ttl)}")

    # Surrogate-Control for CDNs (Fastly, Cloudflare honor it in many setups)
    _merge_header(resp, "Surrogate-Control", f"max-age={int(surrogate_ttl)}")

    # Surrogate keys for tag-based purging
    app_name = cfg.get("APP_NAME", "app")
    release_sha = cfg.get("RELEASE_SHA", "dev")
    base_keys: List[str] = [f"app:{app_name}", f"release:{release_sha}"]
    if keys:
        base_keys.extend(list(keys))

    # Fastly uses space-separated Surrogate-Key
    resp.headers["Surrogate-Key"] = " ".join(sorted(set(k for k in base_keys if k)))

    # Cloudflare tag header (Enterprise)
    resp.headers["Cache-Tag"] = ",".join(sorted(set(k for k in base_keys if k)))

    # ETag
    if enable_etag is None:
        enable_etag = bool(cfg.get("ENABLE_ETAG", True))
    if enable_etag and resp.direct_passthrough is False:
        try:
            payload = resp.get_data()  # type: ignore
            resp.set_etag(_compute_etag(payload, release_sha))
        except Exception:
            pass

    # Last-Modified fallback
    resp.headers.setdefault("Last-Modified", time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()))

    return resp


def no_cache(resp: Response) -> Response:
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    # Also clear surrogate headers
    resp.headers.pop("Surrogate-Control", None)
    resp.headers.pop("Surrogate-Key", None)
    resp.headers.pop("Cache-Tag", None)
    return resp

