import functools
import threading
import time
from typing import Callable

from flask import Flask, jsonify, request, Response

from .config import Config
from .orchestrator import Orchestrator
from .proxy import ReverseProxy
import requests


def create_app() -> Flask:
    cfg = Config()
    app = Flask(__name__)

    orch = Orchestrator(
        blue_url=cfg.blue_url,
        green_url=cfg.green_url,
        strategy=cfg.default_strategy,
        active=cfg.default_active,
        blue_weight=cfg.default_blue_weight,
        green_weight=cfg.default_green_weight,
    )
    proxy = ReverseProxy(orch, timeout=cfg.proxy_timeout, sticky_sessions=cfg.sticky_sessions)

    # Optional bearer token protection
    def require_auth(f: Callable):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if cfg.orch_token:
                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or auth.split(" ", 1)[1] != cfg.orch_token:
                    return jsonify({"error": "unauthorized"}), 401
            return f(*args, **kwargs)
        return wrapper

    # Background health checker
    stop_event = threading.Event()

    def health_checker():
        while not stop_event.is_set():
            for color in ("blue", "green"):
                try:
                    url = orch.get_status()[color]["url"].rstrip("/") + cfg.health_path
                    r = requests.get(url, timeout=2)
                    orch.update_health(color, r.status_code == 200)
                except Exception:
                    orch.update_health(color, False)
            stop_event.wait(5)

    t = threading.Thread(target=health_checker, daemon=True)
    t.start()

    @app.route("/health", methods=["GET"])  # Router health
    def health():
        status = orch.get_status()
        return jsonify({"status": "ok", **status})

    # Orchestration API
    @app.route("/orchestration/status", methods=["GET"])
    @require_auth
    def orchestration_status():
        return jsonify(orch.get_status())

    @app.route("/orchestration/strategy", methods=["POST"])
    @require_auth
    def orchestration_set_strategy():
        body = request.get_json(silent=True) or {}
        strategy = body.get("strategy")
        try:
            status = orch.set_strategy(strategy)
            return jsonify(status)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/orchestration/bluegreen/activate", methods=["POST"])
    @require_auth
    def orchestration_activate():
        body = request.get_json(silent=True) or {}
        active = body.get("active")
        try:
            status = orch.activate(active)
            return jsonify(status)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/orchestration/canary/weights", methods=["POST"])
    @require_auth
    def orchestration_weights():
        body = request.get_json(silent=True) or {}
        blue = body.get("blue")
        green = body.get("green")
        normalize = body.get("normalize", True)
        if blue is None or green is None:
            return jsonify({"error": "blue and green weights required"}), 400
        try:
            status = orch.set_weights(int(blue), int(green), normalize=bool(normalize))
            return jsonify(status)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/orchestration/canary/shift", methods=["POST"])
    @require_auth
    def orchestration_shift():
        body = request.get_json(silent=True) or {}
        delta = int(body.get("delta", 10))
        towards = body.get("towards", "green")
        try:
            status = orch.shift_canary(delta, towards=towards)
            return jsonify(status)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # Catch-all proxy route; keep last
    @app.route('/', defaults={'path': ''}, methods=[
        'GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'
    ])
    @app.route('/<path:path>', methods=[
        'GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'
    ])
    def proxy_route(path):
        # Allow local endpoints to be handled by Flask routes above
        if path.startswith('orchestration') or path == 'health':
            return jsonify({"error": "reserved path"}), 404
        return proxy.forward()

    # Graceful shutdown hook
    @app.before_serving
    def _announce_start():
        app.logger.info("Router starting with config: %s", orch.get_status())

    @app.after_serving
    def _announce_stop():
        stop_event.set()
        t.join(timeout=2)

    return app


if __name__ == "__main__":
    cfg = Config()
    app = create_app()
    app.run(host=cfg.host, port=cfg.port)

