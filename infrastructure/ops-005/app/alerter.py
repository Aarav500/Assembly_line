import json
import smtplib
from email.message import EmailMessage
from typing import Optional

import httpx

from .config import AlertsConfig


class Alerter:
    def __init__(self, alerts: AlertsConfig):
        self.alerts = alerts

    async def send_slack(self, text: str) -> None:
        if not self.alerts.slack_webhook_url:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                await client.post(self.alerts.slack_webhook_url, json={"text": text})
            except Exception:
                pass

    def send_email(self, subject: str, body: str) -> None:
        if not self.alerts.email.enabled:
            return
        cfg = self.alerts.email
        if not (cfg.smtp_host and cfg.from_addr and cfg.to_addrs):
            return
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg.from_addr
        msg["To"] = ", ".join(cfg.to_addrs)
        msg.set_content(body)
        try:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as s:
                if cfg.smtp_user and cfg.smtp_password:
                    s.starttls()
                    s.login(cfg.smtp_user, cfg.smtp_password)
                s.send_message(msg)
        except Exception:
            pass

    async def alert_budget(self, level: str, message: str) -> None:
        await self.send_slack(f":rotating_light: Budget {level.upper()} alert: {message}")
        self.send_email(f"Budget {level} alert", message)

