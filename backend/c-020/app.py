import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from flask import Flask, jsonify, make_response, request

import config
from cache import (
    cache_entry,
    get_cache,
    invalidate_keys,
    invalidate_tags,
    key_for,
    namespaced,
    set_cache,
)

app = Flask(__name__)


# Simulated datastore
_FAKE_DB: Dict[int, Dict] = {}


def _load_item(item_id: int) -> Dict:
    # simulate slow origin fetch
    time.sleep(0.05)
    now = datetime.now(timezone.utc)
    if item_id not in _FAKE_DB:
        _FAKE_DB[item_id] = {
            "id": item_id,
            "value": f"item-{item_id}",
            "updated_at": now.isoformat(),
        }
    # mutate occasionally to simulate updates
    return _FAKE_DB[item_id]


@app.after_request
def add_default_cache_headers(resp):
    # For CDN friendliness across Varnish and Cloud CDN, set sane defaults for non-API routes
    if resp.direct_passthrough:
        return resp
    if request.path.startswith("/api/"):
        return resp
    # Cache static-ish pages for short time at CDN
    resp.headers.setdefault(
        "Cache-Control", "public, max-age=60, s-maxage=300, stale-while-revalidate=60, stale-if-error=86400"
    )
    resp.headers.setdefault("Surrogate-Control", "max-age=300")
    resp.headers.setdefault("Vary", "Accept-Encoding")
    return resp


@app.route("/api/data/<int:item_id>", methods=["GET"])
def get_data(item_id: int):
    bypass = request.args.get("fresh") in {"1", "true", "yes"}
    cache_key = key_for("api:data", item_id)
    cache_tags = {f"item:{item_id}", "api:data"}

    cached = None if bypass else get_cache(cache_key)

    x_cache = "MISS"
    if cached:
        try:
            payload = json.loads(cached)
            x_cache = "HIT"
        except Exception:
            payload = None
    else:
        payload = None

    if payload is None:
        record = _load_item(item_id)
        payload_obj = {
            "item": record,
            "cached": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        body, extra_headers, tags, ttl = cache_entry(
            payload_obj,
            extra_headers={
                # CDN-friendly headers
                "Cache-Control": "public, max-age=60, s-maxage=300, stale-while-revalidate=60, stale-if-error=86400",
                "Surrogate-Control": "max-age=300",
                "Cache-Tags": ",".join(sorted(cache_tags)),
                "Vary": "Accept-Encoding",
            },
            tags=cache_tags,
            ttl=config.DEFAULT_TTL,
        )
        set_cache(cache_key, body, ttl, tags)
        payload = json.loads(body)
    else:
        payload["cached"] = True

    # Conditional request handling based on ETag and Last-Modified
    # Recompute ETag from the payload; store last_modified in payload if present
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    etag = __import__("hashlib").sha256(payload_str.encode("utf-8")).hexdigest()
    last_modified = payload.get("item", {}).get("updated_at")

    if last_modified:
        try:
            last_modified_dt = datetime.fromisoformat(last_modified)
        except Exception:
            last_modified_dt = datetime.now(timezone.utc)
    else:
        last_modified_dt = datetime.now(timezone.utc)

    # ETag check
    inm = request.headers.get("If-None-Match")
    if inm and etag in [t.strip('"') for t in inm.split(",")]:
        resp = make_response("", 304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=60, s-maxage=300, stale-while-revalidate=60, stale-if-error=86400"
        resp.headers["Surrogate-Control"] = "max-age=300"
        resp.headers["Cache-Tags"] = ",".join(sorted(cache_tags))
        resp.headers["Vary"] = "Accept-Encoding"
        resp.headers["X-Cache-Status"] = x_cache
        return resp

    # If-Modified-Since check (best-effort)
    ims = request.headers.get("If-Modified-Since")
    if ims:
        try:
            ims_dt = datetime.strptime(ims, "%a, %d %b %Y %H:%M:%S %Z")
            if last_modified_dt.replace(tzinfo=None) <= ims_dt:
                resp = make_response("", 304)
                resp.headers["ETag"] = etag
                resp.headers["Last-Modified"] = last_modified_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
                resp.headers["Cache-Control"] = "public, max-age=60, s-maxage=300, stale-while-revalidate=60, stale-if-error=86400"
                resp.headers["Surrogate-Control"] = "max-age=300"
                resp.headers["Cache-Tags"] = ",".join(sorted(cache_tags))
                resp.headers["Vary"] = "Accept-Encoding"
                resp.headers["X-Cache-Status"] = x_cache
                return resp
        except Exception:
            pass

    resp = make_response(jsonify(payload))
    resp.headers["ETag"] = etag
    resp.headers["Last-Modified"] = last_modified_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    resp.headers["Cache-Control"] = "public, max-age=60, s-maxage=300, stale-while-revalidate=60, stale-if-error=86400"
    resp.headers["Surrogate-Control"] = "max-age=300"
    resp.headers["Cache-Tags"] = ",".join(sorted(cache_tags))
    resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["X-Cache-Status"] = x_cache
    return resp


@app.route("/api/data/<int:item_id>", methods=["PUT"])
def update_data(item_id: int):
    body = request.get_json(silent=True) or {}
    value = body.get("value", f"item-{item_id}-updated")
    now = datetime.now(timezone.utc)
    _FAKE_DB[item_id] = {"id": item_id, "value": value, "updated_at": now.isoformat()}

    # Invalidate caches by tag and URL
    tags = [f"item:{item_id}", "api:data"]
    deleted = invalidate_tags(tags)

    try:
        ban_varnish(tags=tags)
    except Exception:
        pass

    return jsonify({"status": "ok", "deleted_cache_keys": deleted, "item": _FAKE_DB[item_id]})


@app.route("/purge", methods=["POST"])
def purge():
    token = request.headers.get("X-Purge-Token")
    if token != config.PURGE_TOKEN:
        return jsonify({"error": "unauthorized"}), 403

    payload = request.get_json(silent=True) or {}
    tags: List[str] = payload.get("tags", []) or []
    url_regex: Optional[str] = payload.get("url_regex")
    keys: List[str] = payload.get("redis_keys", []) or []

    deleted = 0
    if tags:
        deleted += invalidate_tags(tags)
    if keys:
        namespaced_keys = [k if k.startswith(config.CACHE_NAMESPACE + ":") else namespaced(k) for k in keys]
        deleted += invalidate_keys(namespaced_keys)

    varnish_ok = False
    try:
        varnish_ok = ban_varnish(tags=tags, url_regex=url_regex)
    except Exception as e:
        varnish_ok = False

    return jsonify({"status": "ok", "redis_deleted": deleted, "varnish": varnish_ok})


def ban_varnish(tags: Optional[List[str]] = None, url_regex: Optional[str] = None) -> bool:
    host = os.environ.get("VARNISH_HOST", config.VARNISH_HOST)
    port = int(os.environ.get("VARNISH_PORT", str(config.VARNISH_PORT)))
    url = f"http://{host}:{port}/"

    headers = {
        "X-Purge-Token": config.PURGE_TOKEN,
    }
    if tags:
        # Build a regex that matches any of the provided tags in Cache-Tags header
        safe_tags = [re.escape(t) for t in tags]
        headers["X-Ban-Cache-Tags"] = "(|)".join(safe_tags) if len(safe_tags) == 1 else "|".join(safe_tags)
    if url_regex:
        headers["X-Ban-URL-Regex"] = url_regex

    resp = requests.request("BAN", url, headers=headers, timeout=3)
    return resp.status_code in (200, 204)


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



def create_app():
    return app


@app.route('/api/static-content', methods=['GET'])
def _auto_stub_api_static_content():
    return 'Auto-generated stub for /api/static-content', 200
