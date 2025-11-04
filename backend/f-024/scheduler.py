import os
import threading
import time
from alerting import evaluate_rules
from db import SessionLocal


def scheduler_loop(stop_event, interval_seconds: int):
    while not stop_event.is_set():
        try:
            s = SessionLocal()
            evaluate_rules(s)
        except Exception as e:
            print(f"[scheduler] error: {e}")
        finally:
            try:
                s.close()
            except Exception:
                pass
        stop_event.wait(interval_seconds)


def start_scheduler(app=None):
    interval = int(os.environ.get("ALERT_EVAL_INTERVAL_SECONDS", 60))
    stop_event = threading.Event()
    t = threading.Thread(target=scheduler_loop, args=(stop_event, interval), daemon=True)
    t.start()
    print(f"[scheduler] started, interval={interval}s")
    return stop_event

