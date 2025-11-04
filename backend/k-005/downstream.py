import os
import requests
from typing import List, Dict, Any

class DownstreamClient:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    def send_chat_completion(self, messages: List[Dict[str, str]], model: str, temperature: float, top_p: float, max_tokens: int) -> Dict[str, Any]:
        provider = self.config.DOWNSTREAM_PROVIDER.lower()
        if provider == "openai":
            return self._send_openai(messages, model, temperature, top_p, max_tokens)
        else:
            return self._send_generic(messages, model, temperature, top_p, max_tokens)

    def _send_openai(self, messages, model, temperature, top_p, max_tokens):
        url = self.config.OPENAI_BASE_URL.rstrip("/") + "/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        resp = self.session.post(url, headers=headers, json=payload, timeout=self.config.REQUEST_TIMEOUT_SEC)
        if resp.status_code >= 400:
            raise RuntimeError(f"Downstream OpenAI error {resp.status_code}: {resp.text}")
        return resp.json()

    def _send_generic(self, messages, model, temperature, top_p, max_tokens):
        url = self.config.DOWNSTREAM_URL
        if not url:
            raise RuntimeError("DOWNSTREAM_URL must be set for generic provider")
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        resp = self.session.post(url, headers=headers, json=payload, timeout=self.config.REQUEST_TIMEOUT_SEC)
        if resp.status_code >= 400:
            raise RuntimeError(f"Downstream error {resp.status_code}: {resp.text}")
        return resp.json()

