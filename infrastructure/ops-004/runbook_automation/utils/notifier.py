import json
import os
import sys
from urllib import request


class Notifier:
    def __init__(self, config, logger):
        self.config = config or {}
        self.logger = logger

    def notify(self, title: str, message: str, severity: str = "info", incident_id: str = None, extra=None):
        payload = {
            "title": title,
            "message": message,
            "severity": severity,
            "incident_id": incident_id,
            "extra": extra or {},
        }
        if self.config.get("stdout", True):
            print(f"NOTIFY: {json.dumps(payload)}")
        slack = self.config.get("slack", {})
        url = slack.get("webhook_url")
        if url:
            text = f"[{severity}] {title}\n{message}"
            body = {
                "text": text,
                "username": slack.get("username", "runbook-bot"),
                "channel": slack.get("channel"),
            }
            try:
                data = json.dumps(body).encode("utf-8")
                req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with request.urlopen(req, timeout=10) as resp:
                    resp.read()
            except Exception as e:
                self.logger.warning({"event": "notify_slack_failed", "error": str(e)})

