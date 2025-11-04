import os
import json
import requests
from typing import Optional


class SlackNotifier:
    def __init__(self, bot_token: Optional[str], default_channel: Optional[str] = None):
        self.bot_token = bot_token
        self.default_channel = default_channel or "#general"
        self._api_base = "https://slack.com/api"

    def enabled(self) -> bool:
        return bool(self.bot_token)

    def send_message(self, text: str, channel: Optional[str] = None) -> bool:
        if not self.enabled():
            print(f"[SlackNotifier] SLACK_BOT_TOKEN not set. Message not sent: {text}")
            return False
        ch = channel or self.default_channel
        try:
            resp = requests.post(
                f"{self._api_base}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                data=json.dumps({"channel": ch, "text": text}),
                timeout=10,
            )
            data = resp.json()
            if not data.get("ok"):
                print(f"[SlackNotifier] Error sending message: {data}")
                return False
            return True
        except Exception as e:
            print(f"[SlackNotifier] Exception: {e}")
            return False

