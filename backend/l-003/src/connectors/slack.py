import requests
from typing import Any, Dict
from .base import BaseConnector


class SlackConnector(BaseConnector):
    slug = "slack"
    name = "Slack"

    def _check_enabled(self) -> bool:
        return bool(self.config.get("SLACK_BOT_TOKEN"))

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.config.get('SLACK_BOT_TOKEN')}",
            "Content-Type": "application/json; charset=utf-8",
        }

    @property
    def _base(self):
        return "https://slack.com/api"

    def health(self) -> Dict[str, Any]:
        url = f"{self._base}/auth.test"
        r = requests.post(url, headers=self._headers, timeout=10)
        ok = r.status_code == 200 and r.json().get("ok")
        return {"ok": bool(ok), "status_code": r.status_code}

    def search(self, query: str):
        url = f"{self._base}/search.messages"
        params = {"query": query, "count": 20}
        r = requests.get(url, headers=self._headers, params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def op_post_message(self, channel: str, text: str, **kwargs):
        url = f"{self._base}/chat.postMessage"
        payload = {"channel": channel, "text": text}
        payload.update(kwargs or {})
        r = requests.post(url, headers=self._headers, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error")}
        return data

    def op_list_channels(self, limit: int = 100):
        url = f"{self._base}/conversations.list"
        params = {"limit": limit}
        r = requests.get(url, headers=self._headers, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

