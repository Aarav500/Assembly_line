import json
import time
from flask import Blueprint, current_app, render_template, make_response, jsonify, url_for
from .caching import set_cache_headers, no_cache

bp = Blueprint("routes", __name__)


@bp.get("/")
def index():
    version = current_app.config.get("RELEASE_SHA", "dev")
    html = render_template("index.html", version=version)
    resp = make_response(html)
    # Cache homepage lightly, but let CDN store a bit longer
    resp = set_cache_headers(resp, ttl=60, surrogate_ttl=300, keys=["route:index"]) 
    return resp


@bp.get("/api/data")
def api_data():
    payload = {
        "app": current_app.config.get("APP_NAME", "app"),
        "release": current_app.config.get("RELEASE_SHA", "dev"),
        "message": "Hello from Flask with CDN caching!",
        "timestamp": int(time.time()),
    }
    resp = make_response(json.dumps(payload), 200)
    resp.mimetype = "application/json"
    # Dynamic API: short browser TTL, longer surrogate cache
    resp = set_cache_headers(resp, ttl=5, surrogate_ttl=60, keys=["route:api:data"]) 
    return resp


@bp.get("/healthz")
def healthz():
    resp = make_response(jsonify({"status": "ok"}), 200)
    # Never cache health checks
    resp = no_cache(resp)
    return resp


@bp.get("/nocache-demo")
def nocache_demo():
    resp = make_response(jsonify({"now": int(time.time())}), 200)
    return no_cache(resp)


@bp.get("/cache-demo")
def cache_demo():
    # Demonstrate route with explicit surrogate keys
    payload = {"demo": True, "time": int(time.time())}
    resp = make_response(json.dumps(payload), 200)
    resp.mimetype = "application/json"
    resp = set_cache_headers(resp, ttl=30, surrogate_ttl=300, keys=["route:cache-demo", "content:demo-block"])
    return resp

