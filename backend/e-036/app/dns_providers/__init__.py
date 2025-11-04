import os
import json
from typing import Optional, Dict
from .base import BaseDNSProvider
from .cloudflare import CloudflareDNSProvider
from .mock import MockDNSProvider


def provider_from_env(default_name: Optional[str] = None, config: Optional[Dict] = None) -> BaseDNSProvider:
    name = (default_name or os.environ.get("DNS_PROVIDER", "mock")).strip().lower()
    cfg = config or {}

    # Allow passing full config as JSON via env var
    cfg_env = os.environ.get("PROVIDER_CONFIG_JSON")
    if cfg_env:
        try:
            cfg.update(json.loads(cfg_env))
        except Exception:  # noqa: BLE001
            pass

    if name == "cloudflare":
        token = cfg.get("api_token") or os.environ.get("CLOUDFLARE_API_TOKEN")
        if not token:
            raise RuntimeError("Cloudflare provider requires api_token or CLOUDFLARE_API_TOKEN")
        return CloudflareDNSProvider(api_token=token)

    # Default to mock provider
    return MockDNSProvider()

