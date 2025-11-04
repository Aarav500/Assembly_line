from flask import Blueprint, jsonify, request
from sqlalchemy import text

from pools.db import session_scope
from pools.redis_pool import get_redis
from pools.http_client import get_http_client

bp = Blueprint("demo", __name__)


@bp.route("/db", methods=["GET"])
def demo_db():
    with session_scope() as s:
        try:
            result = s.execute(text("SELECT 1 AS value"))
            row = result.mappings().first()
            return jsonify({"db_value": row["value"] if row else None})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


@bp.route("/redis", methods=["GET"])
def demo_redis():
    r = get_redis()
    key = request.args.get("key", "demo:key")
    value = request.args.get("value", "hello")
    try:
        r.set(key, value, ex=60)
        got = r.get(key)
        return jsonify({"key": key, "value": got})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/http", methods=["GET"])
def demo_http():
    client = get_http_client()
    url = request.args.get("url", "https://httpbin.org/delay/1")
    try:
        resp = client.get(url, timeout=5)
        return jsonify({"url": url, "status": resp.status_code, "length": len(resp.content)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

