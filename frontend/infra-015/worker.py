import json
import signal
import sys
import time
import traceback
from typing import Optional

from config import QUEUE_POLL_INTERVAL
from email_queue import claim_next_message, set_status, increment_retry_and_schedule, log_event
from email_sender import render_templates, send_smtp

_RUNNING = True


def _handle_signal(signum, frame):
    global _RUNNING
    _RUNNING = False


def process_one() -> bool:
    row = claim_next_message()
    if not row:
        return False
    msg_pk = row["id"]
    try:
        template_vars = json.loads(row["template_vars"]) if row["template_vars"] else {}
    except Exception:
        template_vars = {}

    try:
        text_body, html_body = render_templates(row["template_name"], template_vars)
        smtp_message_id = send_smtp(
            to_email=row["to_email"],
            subject=row["subject"],
            text_body=text_body,
            html_body=html_body,
            app_message_id=row["message_id"],
        )
        set_status(msg_pk, "sent", smtp_message_id=smtp_message_id)
        return True
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        traceback.print_exc()
        retries = int(row["retries"]) + 1
        max_retries = int(row["max_retries"]) if row["max_retries"] is not None else 0
        if retries > max_retries:
            set_status(msg_pk, "failed", error=err)
        else:
            log_event(msg_pk, "send_failed", err)
            increment_retry_and_schedule(msg_pk, retries)
        return True


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    print("[worker] Started queue worker. Press Ctrl+C to stop.")
    while _RUNNING:
        worked = False
        try:
            worked = process_one()
        except Exception as e:
            print(f"[worker] Unhandled error: {e}")
            traceback.print_exc()
        if not worked:
            time.sleep(QUEUE_POLL_INTERVAL)
    print("[worker] Shutting down.")


if __name__ == "__main__":
    main()

