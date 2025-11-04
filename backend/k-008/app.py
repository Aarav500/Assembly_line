import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import os
from flask import Flask, request, jsonify

from config import Config
from agent_manager import FailoverManager
from agent_sim import agents_blueprint


def create_app(config: Config | None = None) -> Flask:
    app = Flask(__name__)

    # Configure logging
    log_level = getattr(logging, (os.getenv("LOG_LEVEL", "INFO").upper()), logging.INFO)
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    app.logger.setLevel(log_level)

    app.config.from_object(config or Config())

    # Register simulated agent endpoints for testing/demo
    app.register_blueprint(agents_blueprint)

    # Create FailoverManager and store in app context
    retry_policy = {
        "retries": app.config["RETRIES_PER_AGENT"],
        "base": app.config["BACKOFF_BASE"],
        "factor": app.config["BACKOFF_FACTOR"],
        "max_delay": app.config["BACKOFF_MAX"],
        "jitter": app.config["BACKOFF_JITTER"],
    }

    app.failover_manager = FailoverManager(
        agent_urls=app.config["AGENT_ENDPOINTS"],
        request_timeout=app.config["REQUEST_TIMEOUT"],
        retry_policy=retry_policy,
        logger=app.logger,
    )

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "agents": app.config["AGENT_ENDPOINTS"],
            "retry_policy": retry_policy,
        })

    @app.post("/query")
    def query_agents():
        try:
            incoming = request.get_json(silent=True) or {}
        except Exception:
            incoming = {}

        # Optional headers to forward
        forward_headers = {}
        for h in ("X-Request-ID", "X-Correlation-ID"):
            if h in request.headers:
                forward_headers[h] = request.headers[h]

        try:
            result = app.failover_manager.call(payload=incoming, headers=forward_headers)
            return jsonify({
                "ok": True,
                "selected_agent": result.get("agent_url"),
                "agent_index": result.get("agent_index"),
                "attempts": result.get("attempts"),
                "per_agent_attempts": result.get("per_agent_attempts"),
                "response": result.get("response"),
            })
        except Exception as e:
            app.logger.exception("All agents failed")
            return jsonify({
                "ok": False,
                "error": str(e),
                "errors": getattr(e, "errors", None),
            }), 503

    return app


app = create_app()


if __name__ == "__main__":
    # Use threaded server so internal calls to simulated agents won't deadlock
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), threaded=True)



@app.route('/agents', methods=['GET'])
def _auto_stub_agents():
    return 'Auto-generated stub for /agents', 200
