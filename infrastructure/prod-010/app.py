import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Flask, Response, jsonify, request
from flask_compress import Compress
from werkzeug.http import http_date

app = Flask(__name__)

# Compression configuration (gzip + brotli if available)
app.config["COMPRESS_ALGORITHM"] = ["br", "gzip"]
app.config["COMPRESS_BR_LEVEL"] = 5
app.config["COMPRESS_MIN_SIZE"] = 256  # Only compress responses larger than this many bytes
app.config["COMPRESS_MIMETYPES"] = [
    "application/json",
    "text/html",
    "text/plain",
]
Compress(app)

# In-memory store for demo purposes
# Each item keeps an updated_at timestamp for Last-Modified
ITEMS: Dict[str, Dict[str, Any]] = {
    "1": {
        "id": "1",
        "name": "Alpha",
        "updated_at": datetime.now(timezone.utc),
    },
    "2": {
        "id": "2",
        "name": "Beta",
        "updated_at": datetime.now(timezone.utc),
    },
}


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_etag(body: bytes) -> str:
    # Strong ETag from SHA-256 of the canonical representation
    return hashlib.sha256(body).hexdigest()


def add_vary_header(resp: Response, value: str) -> None:
    existing = resp.headers.get("Vary")
    if existing:
        values = {v.strip() for v in existing.split(",") if v.strip()}
        if value not in values:
            values.add(value)
            resp.headers["Vary"] = ", ".join(sorted(values))
    else:
        resp.headers["Vary"] = value


def build_conditional_response(
    payload: Any,
    last_modified: Optional[datetime],
    cache_seconds: int = 60,
    status: int = 200,
) -> Response:
    body = canonical_json_bytes(payload)
    etag_value = compute_etag(body)

    # Conditional requests handling
    # 1) If-None-Match (ETag)
    inm = request.if_none_match
    if inm and inm.contains(etag_value, weak=False):
        resp = Response(status=304)
        resp.set_etag(etag_value, weak=False)
        if last_modified is not None:
            resp.headers["Last-Modified"] = http_date(last_modified.timestamp())
        resp.cache_control.public = True
        resp.cache_control.max_age = cache_seconds
        add_vary_header(resp, "Accept-Encoding")
        return resp

    # 2) If-Modified-Since (time-based)
    ims = request.if_modified_since
    if ims and last_modified is not None and last_modified <= ims:
        resp = Response(status=304)
        resp.set_etag(etag_value, weak=False)
        resp.headers["Last-Modified"] = http_date(last_modified.timestamp())
        resp.cache_control.public = True
        resp.cache_control.max_age = cache_seconds
        add_vary_header(resp, "Accept-Encoding")
        return resp

    # Build normal 200/201/etc response
    resp = Response(body, status=status, mimetype="application/json; charset=utf-8")
    resp.set_etag(etag_value, weak=False)
    if last_modified is not None:
        resp.headers["Last-Modified"] = http_date(last_modified.timestamp())
    resp.cache_control.public = True
    resp.cache_control.max_age = cache_seconds
    add_vary_header(resp, "Accept-Encoding")

    # HEAD should not include a body, but preserve headers. For correctness,
    # set Content-Length to the length the GET would have returned.
    if request.method == "HEAD":
        resp.headers["Content-Length"] = str(len(body))
        resp.set_data(b"")

    return resp


@app.route("/api/health", methods=["GET", "HEAD"])
def health() -> Response:
    payload = {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
    # This is a dynamic response; use now for last-modified
    return build_conditional_response(payload, datetime.now(timezone.utc), cache_seconds=5)


@app.route("/api/items", methods=["GET", "HEAD"])
def list_items() -> Response:
    # Expose items without the Python datetime object (serialize to ISO 8601)
    def serialize(item: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(item)
        out["updated_at"] = out["updated_at"].isoformat()
        return out

    data = [serialize(item) for item in ITEMS.values()]

    # Last-Modified of collection = max of items
    last_mod = max((it["updated_at"] for it in ITEMS.values()), default=datetime.now(timezone.utc))
    return build_conditional_response({"items": data}, last_mod, cache_seconds=30)


def get_item_and_payload(item_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    item = ITEMS.get(item_id)
    if not item:
        return None, None
    payload = {
        "id": item["id"],
        "name": item["name"],
        "updated_at": item["updated_at"].isoformat(),
    }
    return item, payload


@app.route("/api/items/<item_id>", methods=["GET", "HEAD"])
def get_item(item_id: str) -> Response:
    item, payload = get_item_and_payload(item_id)
    if not item:
        return jsonify({"error": "not_found"}), 404
    return build_conditional_response(payload, item["updated_at"], cache_seconds=120)


@app.route("/api/items/<item_id>", methods=["PUT", "PATCH"])
def update_item(item_id: str) -> Response:
    # Upsert semantics for demo simplicity
    body = request.get_json(silent=True) or {}
    name = body.get("name")
    if not isinstance(name, str) or not name:
        return jsonify({"error": "invalid_name"}), 400

    # Compute current ETag for conditional updates (If-Match)
    current_item, current_payload = get_item_and_payload(item_id)
    if current_item is not None and current_payload is not None:
        current_etag = compute_etag(canonical_json_bytes(current_payload))
        if_match = request.if_match
        if if_match and not if_match.contains(current_etag, weak=False):
            # Client required a specific ETag which does not match
            resp = jsonify({"error": "precondition_failed"})
            resp.status_code = 412
            return resp

    now = datetime.now(timezone.utc)
    if item_id not in ITEMS:
        ITEMS[item_id] = {
            "id": item_id,
            "name": name,
            "updated_at": now,
        }
        item, payload = get_item_and_payload(item_id)
        return build_conditional_response(payload, now, cache_seconds=0, status=201)
    else:
        ITEMS[item_id]["name"] = name
        ITEMS[item_id]["updated_at"] = now
        item, payload = get_item_and_payload(item_id)
        return build_conditional_response(payload, now, cache_seconds=0, status=200)


if __name__ == "__main__":
    # For local development only. Use a production WSGI server in production.
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app
