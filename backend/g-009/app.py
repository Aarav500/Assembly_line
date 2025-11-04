import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import os
import time
from flask import Flask, request, jsonify

from config import Config
from cache import Cache
from dedup import Deduper
from inference import InferenceProvider
from utils import hash_request, utc_ts

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("inference-cache")

cache = Cache(Config)
deduper = Deduper(cache, Config)
provider = InferenceProvider()

# Simple metrics
_metrics = {
    "cache_hits": 0,
    "cache_misses": 0,
    "provider_calls": 0,
    "dedup_coalesced": 0,
    "errors": 0,
}

from threading import Lock
_metrics_lock = Lock()

def inc(metric, n=1):
    with _metrics_lock:
        _metrics[metric] = _metrics.get(metric, 0) + n


def _normalize_payload(data):
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    # Support 'prompt' alias to 'input'
    if "input" not in data and "prompt" in data:
        data["input"] = data.pop("prompt")
    if "input" not in data:
        raise ValueError("Missing 'input' in request body")

    model = data.get("model", "default")
    params = data.get("params") or {}
    # Only keep fields that affect output to ensure deterministic cache key
    norm = {
        "model": model,
        "input": data["input"],
        "params": params,
    }
    return norm


@app.route("/infer", methods=["POST"])
def infer():
    started = time.time()
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Invalid or missing JSON body"}), 400
        norm = _normalize_payload(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Cache and dedup options
    skip_cache = request.args.get("nocache") in ("1", "true", "True") or \
                 request.headers.get("X-Bypass-Cache", "").lower() == "true"
    force_refresh = request.args.get("refresh") in ("1", "true", "True") or \
                    request.headers.get("X-Force-Refresh", "").lower() == "true"

    key = hash_request(norm)
    cache_key = f"result:{key}"

    # Fast-path cache lookup
    if not skip_cache and not force_refresh:
        cached = cache.get_json(cache_key)
        if cached is not None:
            inc("cache_hits")
            return jsonify({
                "key": key,
                "cached": True,
                "from": "cache",
                "created_at": cached.get("created_at"),
                "ttl_seconds": cache.ttl(cache_key),
                "result": cached.get("result"),
                "meta": cached.get("meta", {}),
                "duration_ms": int((time.time() - started) * 1000),
            })

    # Deduplicate concurrent identical requests
    handle = deduper.begin(key)

    try:
        # Recheck cache after dedup begins, to avoid duplicate provider calls
        if not skip_cache and not force_refresh:
            cached = cache.get_json(cache_key)
            if cached is not None:
                inc("cache_hits")
                # Allow followers to return without waiting if leader already completed
                try:
                    handle.done()
                except Exception:
                    pass
                return jsonify({
                    "key": key,
                    "cached": True,
                    "from": "cache",
                    "created_at": cached.get("created_at"),
                    "ttl_seconds": cache.ttl(cache_key),
                    "result": cached.get("result"),
                    "meta": cached.get("meta", {}),
                    "duration_ms": int((time.time() - started) * 1000),
                })

        if handle.is_leader:
            # Leader executes the provider call
            inc("cache_misses")
            inc("provider_calls")
            try:
                result = provider.generate(
                    model=norm.get("model"),
                    input_text=norm.get("input"),
                    params=norm.get("params", {}),
                )
            except Exception as e:
                inc("errors")
                logger.exception("Provider error")
                return jsonify({"error": str(e)}), 502

            # Store in cache
            payload = {
                "created_at": utc_ts(),
                "result": result,
                "meta": {
                    "key": key,
                    "model": norm.get("model"),
                },
            }
            cache.set_json(cache_key, payload, ttl=Config.CACHE_TTL_SECONDS)
            # Signal completion
            handle.done()

            return jsonify({
                "key": key,
                "cached": False,
                "from": "provider",
                "created_at": payload["created_at"],
                "ttl_seconds": cache.ttl(cache_key),
                "result": result,
                "meta": payload["meta"],
                "duration_ms": int((time.time() - started) * 1000),
            })
        else:
            # Follower: wait for leader's result or timeout
            waited = handle.wait_for_result(
                cache_key=cache_key,
                timeout=Config.INFLIGHT_WAIT_TIMEOUT_SECONDS,
                poll_interval=Config.INFLIGHT_POLL_INTERVAL_SECONDS,
            )
            if waited is not None:
                inc("dedup_coalesced")
                return jsonify({
                    "key": key,
                    "cached": True,
                    "from": "cache_after_wait",
                    "created_at": waited.get("created_at"),
                    "ttl_seconds": cache.ttl(cache_key),
                    "result": waited.get("result"),
                    "meta": waited.get("meta", {}),
                    "duration_ms": int((time.time() - started) * 1000),
                })
            else:
                inc("errors")
                return jsonify({
                    "error": "Timed out waiting for in-flight request",
                    "key": key,
                }), 504
    finally:
        # Followers have nothing to do here; leaders already called done()
        pass


@app.route("/metrics", methods=["GET"])
def metrics():
    status = {
        "backend": cache.backend,
        "redis": cache.is_redis,
    }
    with _metrics_lock:
        m = dict(_metrics)
    return jsonify({"metrics": m, "status": status})


@app.route("/healthz", methods=["GET"])
def healthz():
    ok = True
    backend = cache.backend
    details = {"backend": backend}
    if cache.is_redis:
        try:
            cache.client.ping()
        except Exception as e:
            ok = False
            details["redis_error"] = str(e)
    return jsonify({"ok": ok, "details": details}), 200 if ok else 500


@app.route("/cache/<key>", methods=["GET"])
def get_cache(key):
    cache_key = f"result:{key}"
    data = cache.get_json(cache_key)
    if data is None:
        return jsonify({"exists": False, "key": key}), 404
    return jsonify({
        "exists": True,
        "key": key,
        "created_at": data.get("created_at"),
        "ttl_seconds": cache.ttl(cache_key),
        "result": data.get("result"),
        "meta": data.get("meta", {}),
    })


@app.route("/cache/<key>", methods=["DELETE"])
def delete_cache(key):
    cache_key = f"result:{key}"
    deleted = cache.delete(cache_key)
    return jsonify({"deleted": bool(deleted), "key": key})


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)



def create_app():
    return app


@app.route('/cache/clear', methods=['POST'])
def _auto_stub_cache_clear():
    return 'Auto-generated stub for /cache/clear', 200


@app.route('/inference', methods=['POST'])
def _auto_stub_inference():
    return 'Auto-generated stub for /inference', 200


@app.route('/cache/stats', methods=['GET'])
def _auto_stub_cache_stats():
    return 'Auto-generated stub for /cache/stats', 200
