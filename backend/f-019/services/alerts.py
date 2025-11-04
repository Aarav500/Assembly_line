import json
import os
import sys
from typing import Optional
import requests

from config import SLACK_WEBHOOK_URL


def send_alert(message: str, channel: Optional[str] = None):
    # Log to stdout
    print(f"ALERT: {message}", file=sys.stdout)
    # Send to Slack if configured
    if SLACK_WEBHOOK_URL:
        payload = {
            'text': message
        }
        try:
            r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
            r.raise_for_status()
        except Exception as e:
            print(f"Failed to send Slack alert: {e}", file=sys.stderr)

