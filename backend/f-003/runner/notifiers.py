from __future__ import annotations
import json
import smtplib
from email.mime.text import MIMEText
from typing import List, Dict
import requests

from .config import Config


class BaseNotifier:
    name = "base"
    def send(self, title: str, message: str) -> bool:
        raise NotImplementedError


class LoggerNotifier(BaseNotifier):
    name = "log"
    def send(self, title: str, message: str) -> bool:
        print(f"[ALERT] {title}: {message}")
        return True


class SlackNotifier(BaseNotifier):
    name = "slack"
    def __init__(self, webhook_url: str | None):
        self.webhook_url = webhook_url
    def send(self, title: str, message: str) -> bool:
        if not self.webhook_url:
            return False
        payload = {"text": f"*{title}*\n{message}"}
        try:
            r = requests.post(self.webhook_url, json=payload, timeout=10)
            return 200 <= r.status_code < 300
        except Exception:
            return False


class WebhookNotifier(BaseNotifier):
    name = "webhook"
    def __init__(self, url: str | None):
        self.url = url
    def send(self, title: str, message: str) -> bool:
        if not self.url:
            return False
        try:
            r = requests.post(self.url, json={"title": title, "message": message}, timeout=10)
            return 200 <= r.status_code < 300
        except Exception:
            return False


class EmailNotifier(BaseNotifier):
    name = "email"
    def __init__(self, host: str | None, port: int | None, tls: bool, user: str | None, password: str | None, sender: str | None, recipient: str | None):
        self.host = host
        self.port = port
        self.tls = tls
        self.user = user
        self.password = password
        self.sender = sender
        self.recipient = recipient
    def send(self, title: str, message: str) -> bool:
        if not all([self.host, self.port, self.sender, self.recipient]):
            return False
        try:
            msg = MIMEText(message)
            msg['Subject'] = title
            msg['From'] = self.sender
            msg['To'] = self.recipient

            server = smtplib.SMTP(self.host, self.port)
            if self.tls:
                server.starttls()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.sendmail(self.sender, [self.recipient], msg.as_string())
            server.quit()
            return True
        except Exception:
            return False


class NotifierManager:
    def __init__(self, config: Config):
        self.config = config
        self.notifiers: Dict[str, BaseNotifier] = {}
        self._init_notifiers()

    def _init_notifiers(self):
        settings = self.config.alerting.settings
        # Always have a logger
        self.notifiers["log"] = LoggerNotifier()
        # Slack
        self.notifiers["slack"] = SlackNotifier(settings.slack_webhook_url)
        # Generic webhook
        self.notifiers["webhook"] = WebhookNotifier(settings.webhook_url)
        # Email
        self.notifiers["email"] = EmailNotifier(
            host=settings.email_host,
            port=settings.email_port,
            tls=settings.email_tls,
            user=settings.email_user,
            password=settings.email_password,
            sender=settings.email_from,
            recipient=settings.email_to,
        )

    def send(self, channels: List[str], title: str, message: str) -> List[str]:
        sent = []
        for ch in channels:
            n = self.notifiers.get(ch)
            if not n:
                continue
            ok = n.send(title, message)
            if ok:
                sent.append(ch)
        return sent

