import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, make_response

import router
import traffic_switcher as ts
from app_blue import handlers as blue
from app_green import handlers as green

app = Flask(__name__)

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
COOKIE_NAME = "bg_variant"


def _require_admin():
    if not ADMIN_TOKEN:
        return None
    token = request.headers.get("X-Admin-Token")
    if token == ADMIN_TOKEN:
        return None
    return make_response(jsonify({"error": "unauthorized"}), 401)


def _set_variant_cookie_if_needed(resp, variant, cfg):
    # Set sticky cookie only if configured and not already present
    if not cfg.get("respect_sticky", True):
        return resp
    existing = request.cookies.get(COOKIE_NAME)
    if existing == variant:
        return resp
    max_age = int(cfg.get("cookie_max_age", 7 * 24 * 3600))
    resp.set_cookie(COOKIE_NAME, variant, max_age=max_age, httponly=False, samesite="Lax")
    return resp


def _call_handler(handler):
    result = handler()
    if isinstance(result, tuple):
        return make_response(*result)
    return make_response(result)


@app.route("/", methods=["GET"]) 
def root():
    cfg = ts.get_config()
    decision = router.choose_variant(request, cfg)
    variant = decision.variant
    if variant == "blue":
        resp = _call_handler(blue.index)
    else:
        resp = _call_handler(green.index)
    resp.headers["X-BG-Variant"] = variant
    resp.headers["X-BG-Decision-Source"] = decision.source
    return _set_variant_cookie_if_needed(resp, variant, cfg)


@app.route("/api/hello", methods=["GET"]) 
def api_hello():
    cfg = ts.get_config()
    decision = router.choose_variant(request, cfg)
    variant = decision.variant
    if variant == "blue":
        resp = _call_handler(blue.hello)
    else:
        resp = _call_handler(green.hello)
    resp.headers["X-BG-Variant"] = variant
    resp.headers["X-BG-Decision-Source"] = decision.source
    return _set_variant_cookie_if_needed(resp, variant, cfg)


@app.route("/health", methods=["GET"]) 
def health():
    cfg = ts.get_config()
    return jsonify({
        "status": "ok",
        "split": {
            "blue_percent": cfg.get("blue_percent", 100),
            "green_percent": 100 - int(cfg.get("blue_percent", 100))
        },
        "respect_sticky": cfg.get("respect_sticky", True)
    })


# Direct version endpoints (debug/testing)
@app.route("/blue", methods=["GET"]) 
def blue_direct():
    return _call_handler(blue.index)


@app.route("/green", methods=["GET"]) 
def green_direct():
    return _call_handler(green.index)


@app.route("/whoami", methods=["GET"]) 
def whoami():
    cfg = ts.get_config()
    decision = router.choose_variant(request, cfg)
    cookie_variant = request.cookies.get(COOKIE_NAME)
    return jsonify({
        "decided_variant": decision.variant,
        "decision_source": decision.source,
        "cookie_variant": cookie_variant,
        "split": cfg.get("blue_percent", 100)
    })


# Admin endpoints
@app.route("/admin/config", methods=["GET"]) 
def admin_get_config():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    return jsonify(ts.get_config())


@app.route("/admin/config", methods=["POST"]) 
def admin_set_config():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    payload = request.get_json(force=True, silent=True) or {}
    resp = {}
    if "blue_percent" in payload:
        blue_percent = int(payload.get("blue_percent"))
        ts.set_split(blue_percent)
        resp["blue_percent"] = blue_percent
    if "respect_sticky" in payload:
        respect = bool(payload.get("respect_sticky"))
        ts.set_respect_sticky(respect)
        resp["respect_sticky"] = respect
    if "cookie_max_age" in payload:
        ts.set_cookie_max_age(int(payload.get("cookie_max_age")))
        resp["cookie_max_age"] = int(payload.get("cookie_max_age"))
    return jsonify({"status": "updated", **resp, "config": ts.get_config()})


@app.route("/admin/switch", methods=["POST"]) 
def admin_switch():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    new_percent = ts.toggle()
    return jsonify({"status": "ok", "blue_percent": new_percent, "green_percent": 100 - new_percent})


@app.route("/admin/promote", methods=["POST"]) 
def admin_promote():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    payload = request.get_json(force=True, silent=True) or {}
    version = payload.get("version", "green").lower()
    if version not in ("blue", "green"):
        return make_response(jsonify({"error": "version must be 'blue' or 'green'"}), 400)
    ts.set_all(version)
    cfg = ts.get_config()
    return jsonify({"status": "ok", "blue_percent": cfg["blue_percent"], "green_percent": 100 - cfg["blue_percent"]})


@app.route("/admin/rollback", methods=["POST"]) 
def admin_rollback():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    # Rollback means 100% blue
    ts.set_all("blue")
    cfg = ts.get_config()
    return jsonify({"status": "ok", "blue_percent": cfg["blue_percent"], "green_percent": 100 - cfg["blue_percent"]})


@app.route("/admin/respect_sticky", methods=["POST"]) 
def admin_respect_sticky():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    payload = request.get_json(force=True, silent=True) or {}
    respect = bool(payload.get("respect_sticky", True))
    ts.set_respect_sticky(respect)
    return jsonify({"status": "ok", "respect_sticky": respect, "config": ts.get_config()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app


@app.route('/switch/green', methods=['GET'])
def _auto_stub_switch_green():
    return 'Auto-generated stub for /switch/green', 200
