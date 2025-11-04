#!/usr/bin/env python3
import os
import signal
import sys
import time

# Allow running from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import Config
from app.failover import FailoverManager


stop = False

def handle_signal(signum, frame):
    global stop
    stop = True


def main() -> int:
    interval = int(os.getenv("MONITOR_INTERVAL_SECONDS", "15"))
    cfg = Config()
    mgr = FailoverManager(cfg)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"Starting health monitor loop, interval={interval}s")
    while not stop:
        try:
            cfg.validate()
            result = mgr.evaluate_and_act()
            action = result.get("decision", {}).get("action")
            if action and action != "none":
                print(f"Action taken: {action} -> {result.get('decision')}")
            else:
                print("Checked: no action needed")
        except Exception as e:
            print(f"Monitor error: {e}", file=sys.stderr)
        # Sleep in small steps to react to stop flag
        for _ in range(interval):
            if stop:
                break
            time.sleep(1)
    print("Monitor stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

