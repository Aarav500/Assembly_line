from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

from pools.db import ping_db
from pools.redis_pool import ping_redis
from pools.http_client import get_http_client

bp = Blueprint("health", __name__)


@bp.route("/healthz", methods=["GET"])  # Liveness and readiness combined
def healthz():
    status = {
        "status": "ok",
        "components": {
            "database": {"ok": False, "latency_ms": None},
            "redis": {"ok": False},
            "external_http": {"ok": False, "status": None},
        },
    }

    # DB check
    db_ok = ping_db()
    status["components"]["database"]["ok"] = bool(db_ok)

    # Redis check
    status["components"]["redis"]["ok"] = ping_redis()

    # External HTTP check
    client = get_http_client()
    url = current_app.config.get("HEALTHCHECK_EXTERNAL_URL")
    try:
        resp = client.get(url, timeout=3)
        status["components"]["external_http"] = {"ok": resp.ok, "status": resp.status_code}
    except Exception as exc:
        status["components"]["external_http"] = {"ok": False, "status": str(exc)}

    overall_ok = all(
        [
            status["components"]["database"]["ok"],
            status["components"]["redis"]["ok"],
            status["components"]["external_http"]["ok"],
        ]
    )
    http_status = 200 if overall_ok else 503
    status["status"] = "ok" if overall_ok else "degraded"
    return jsonify(status), http_status

