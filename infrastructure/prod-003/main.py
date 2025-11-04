import logging
import signal
import sys
import time

from app.logging_config import setup_logging
from app.health import HealthMonitor
from app.service import breaker, get_user_safe, list_users_safe


def main() -> int:
    setup_logging()
    log = logging.getLogger("app")

    monitor = HealthMonitor(breaker=breaker)
    monitor.start()

    log.info("Demo starting. Press Ctrl+C to exit.")

    def _sigint(_signum, _frame):
        log.info("Shutting down...")
        monitor.stop(2.0)
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)

    # Demo loop: periodically attempt DB operations
    i = 0
    while True:
        i += 1
        try:
            res1 = get_user_safe(user_id=1)
            res2 = list_users_safe(limit=5)
            log.info("Attempt %d | health=%s | get_user=%s | list_users=%s", i, monitor.healthy, res1["status"], res2["status"])
        except Exception as exc:  # noqa: BLE001
            log.exception("Unhandled error during DB operations: %s", exc)
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())

