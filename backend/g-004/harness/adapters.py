import requests
from typing import Any, Dict
import config


class ModelAdapter:
    def __init__(self, name: str):
        self.name = name

    def generate(self, prompt: str, item: Dict[str, Any] | None = None, params: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError


class EchoAdapter(ModelAdapter):
    def __init__(self):
        super().__init__("echo")

    def generate(self, prompt: str, item=None, params=None) -> str:
        return prompt


class RegexReplaceAdapter(ModelAdapter):
    def __init__(self, pattern: str, replacement: str):
        super().__init__("regex-replace")
        self.pattern = pattern
        self.replacement = replacement

    def generate(self, prompt: str, item=None, params=None) -> str:
        import re
        return re.sub(self.pattern, self.replacement, prompt)


class HTTPModelAdapter(ModelAdapter):
    def __init__(self, url: str, method: str = "POST", headers: Dict[str, str] | None = None, prompt_key: str = "prompt", response_path: str = "text"):
        super().__init__("http")
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.prompt_key = prompt_key
        self.response_path = response_path

    def generate(self, prompt: str, item=None, params=None) -> str:
        payload = {self.prompt_key: prompt}
        if params and isinstance(params, dict):
            payload.update(params)
        timeout = config.HTTP_TIMEOUT
        if self.method == "POST":
            resp = requests.post(self.url, json=payload, headers=self.headers, timeout=timeout)
        else:
            resp = requests.get(self.url, params=payload, headers=self.headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text}
        # Traverse response_path by dots to extract text
        val = data
        for part in self.response_path.split('.'):
            if isinstance(val, dict) and part in val:
                val = val[part]
            else:
                break
        return str(val)


def build_adapter(spec: Dict[str, Any]) -> ModelAdapter:
    if not isinstance(spec, dict):
        raise ValueError("Model spec must be an object")
    mtype = (spec.get("type") or "").lower()
    if mtype == "echo":
        return EchoAdapter()
    if mtype == "regex-replace":
        pattern = spec.get("pattern", "")
        replacement = spec.get("replacement", "")
        return RegexReplaceAdapter(pattern, replacement)
    if mtype == "http":
        url = spec.get("url")
        if not url:
            raise ValueError("For type 'http', field 'url' is required")
        method = spec.get("method", "POST")
        headers = spec.get("headers")
        prompt_key = spec.get("prompt_key", "prompt")
        response_path = spec.get("response_path", "text")
        return HTTPModelAdapter(url, method=method, headers=headers, prompt_key=prompt_key, response_path=response_path)
    raise ValueError(f"Unknown model type: {mtype}")

