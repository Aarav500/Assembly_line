import logging
import os
import signal
import sys
import threading
import time
from typing import Optional

from werkzeug.serving import make_server

from app import app as flask_app
from app.cleanup import cleanup_manager
from app.resources import Heartbeat

logger = logging.getLogger("graceful-server")


class GracefulHTTPServer:
    def __init__(self, app, host: str, port: int, threaded: bool = True):
        self._app = app
        self._host = host
        self._port = port
        self._threaded = threaded
        self._server = make_server(self._host, self._port, self._app, threaded=self._threaded)
        self._shutdown_initiated = threading.Event()
        self._drain_started = threading.Event()
        self._server_thread: Optional[threading.Thread] = None

    def serve(self):
        logger.info("Starting server on %s:%d (threaded=%s)", self._host, self._port, self._threaded)
        self._install_signal_handlers()

        # Example background resource - register cleanup
        hb = Heartbeat(interval=float(os.getenv("HEARTBEAT_INTERVAL", "5")))
        hb.start()
        cleanup_manager.register("heartbeat", hb.stop)

        try:
            self._server.serve_forever()
        finally:
            # Once serve_forever exits, perform final drain wait and cleanup
            self._post_shutdown_cleanup()

    def _install_signal_handlers(self):
        def handler(signum, frame):
            if not self._shutdown_initiated.is_set():
                logger.info("Received signal %s - initiating graceful shutdown", signum)
                self._shutdown_initiated.set()
                self._start_draining_and_schedule_shutdown()
            else:
                logger.info("Signal %s received but shutdown already in progress", signum)

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, handler)
            except Exception:
                # Some platforms may not support certain signals
                pass

    def _start_draining_and_schedule_shutdown(self):
        if self._drain_started.is_set():
            return
        self._drain_started.set()

        drain_timeout = float(os.getenv("DRAIN_TIMEOUT", "25"))
        logger.info("Marking app as draining and scheduling shutdown in up to %.2fs", drain_timeout)

        # Mark the app as draining so health checks fail and new requests are rejected
        self._app.start_draining()

        def drainer():
            drained, remaining = self._app.wait_for_zero(drain_timeout)
            if drained:
                logger.info("All in-flight requests drained before timeout")
            else:
                logger.warning("Drain timeout reached with %d in-flight request(s)", remaining)
            logger.info("Stopping server from accepting new connections")
            try:
                self._server.shutdown()
            except Exception as e:
                logger.exception("Error calling server.shutdown(): %s", e)

        t = threading.Thread(target=drainer, name="Drainer", daemon=True)
        t.start()

    def _post_shutdown_cleanup(self):
        # After server stops accepting, wait a bit more for any lingering tasks
        post_stop_wait = float(os.getenv("POST_STOP_DRAIN_WAIT", "5"))
        if post_stop_wait > 0:
            logger.info("Waiting up to %.2fs for remaining in-flight requests to finish", post_stop_wait)
            drained, remaining = self._app.wait_for_zero(post_stop_wait)
            if drained:
                logger.info("All in-flight requests completed after server stop")
            else:
                logger.warning("Proceeding with cleanup with %d in-flight request(s)", remaining)

        # Run cleanup hooks
        per_hook_timeout = float(os.getenv("CLEANUP_HOOK_TIMEOUT", "5"))
        cleanup_manager.run_all(per_hook_timeout=per_hook_timeout)
        logger.info("Shutdown complete")


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    threaded = os.getenv("THREADED", "true").lower() in ("1", "true", "yes")

    server = GracefulHTTPServer(flask_app, host, port, threaded=threaded)
    try:
        server.serve()
    except Exception as e:
        logger.exception("Server encountered an error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

