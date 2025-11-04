import os
import requests
import uuid


class TokenCostLoggerClient:
    def __init__(self, base_url: str = None, api_key: str = None, timeout: int = 10):
        self.base_url = (base_url or os.environ.get("LOGGER_BASE_URL") or "http://localhost:5000").rstrip("/")
        self.api_key = api_key or os.environ.get("LOGGER_API_KEY")
        self.timeout = timeout

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def log_event(self, workflow_id: str, provider: str = None, model: str = None,
                  prompt_tokens: int = None, completion_tokens: int = None,
                  prompt_text: str = None, completion_text: str = None,
                  prompt_cost_usd: float = None, completion_cost_usd: float = None, total_cost_usd: float = None,
                  run_id: str = None, metadata: dict = None):
        payload = {
            "workflow_id": workflow_id,
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "prompt_text": prompt_text,
            "completion_text": completion_text,
            "prompt_cost_usd": prompt_cost_usd,
            "completion_cost_usd": completion_cost_usd,
            "total_cost_usd": total_cost_usd,
            "run_id": run_id or str(uuid.uuid4()),
            "metadata": metadata or {},
        }
        resp = requests.post(f"{self.base_url}/log", json=payload, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def log_openai_response(self, workflow_id: str, response, provider: str = "openai", model: str = None, run_id: str = None, metadata: dict = None):
        usage = getattr(response, "usage", None) or (response.get("usage") if isinstance(response, dict) else None)
        pt = ct = None
        if usage:
            pt = usage.get("prompt_tokens") if isinstance(usage, dict) else getattr(usage, "prompt_tokens", None)
            ct = usage.get("completion_tokens") if isinstance(usage, dict) else getattr(usage, "completion_tokens", None)
        if model is None:
            model = getattr(response, "model", None) or (response.get("model") if isinstance(response, dict) else None)
        return self.log_event(
            workflow_id=workflow_id,
            provider=provider,
            model=model,
            prompt_tokens=pt,
            completion_tokens=ct,
            run_id=run_id,
            metadata=metadata,
        )

