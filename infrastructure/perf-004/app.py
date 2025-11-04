import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import signal
import sys
from flask import Flask

from config import Config
from monitoring.metrics import init_metrics
from pools.db import init_db, shutdown_db
from pools.redis_pool import init_redis, shutdown_redis
from pools.http_client import init_http_client, shutdown_http_client
from blueprints.health import bp as health_bp
from blueprints.demo import bp as demo_bp


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize monitoring first so other components can register metrics
    init_metrics(app)

    # Initialize resource pools
    init_db(app)
    init_redis(app)
    init_http_client(app)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(demo_bp, url_prefix="/demo")

    # Graceful shutdown hooks
    def graceful_shutdown(*_args):
        try:
            shutdown_http_client(app)
        except Exception:
            pass
        try:
            shutdown_redis(app)
        except Exception:
            pass
        try:
            shutdown_db(app)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    @app.teardown_appcontext
    def _teardown(exception):  # noqa: ARG001
        # Do not shutdown pools here on each request; keep pools process-wide
        return None

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(app.config.get("PORT", 5000)), debug=app.config.get("DEBUG", False))

