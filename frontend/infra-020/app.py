import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import atexit
from datetime import datetime
from flask import Flask, jsonify, render_template
from monitoring import DependencyManager


def create_app():
    app = Flask(__name__)

    config_path = os.environ.get("CONFIG_PATH", "config.yml")
    manager = DependencyManager(config_path=config_path)
    manager.start()

    @app.route("/healthz", methods=["GET"])  # Liveness
    def healthz():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})

    @app.route("/readyz", methods=["GET"])  # Readiness
    def readyz():
        overall = manager.get_overall_status(force_check_if_stale=True)
        code = 200 if overall["overall_status"] == "UP" else 503
        return jsonify(overall), code

    @app.route("/api/status", methods=["GET"])  # JSON status
    def api_status():
        return jsonify(manager.get_overall_status())

    @app.route("/status", methods=["GET"])  # Dashboard
    def status_dashboard():
        ctx = manager.get_overall_status()
        return render_template("status.html", **ctx)

    # Ensure background threads stop when process exits
    def _cleanup():
        manager.stop()

    atexit.register(_cleanup)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



# auto: ensure timedelta
try:
    app.timedelta
except Exception:
    try:
        app.timedelta = {}
    except Exception:
        pass
