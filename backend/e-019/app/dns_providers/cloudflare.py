from typing import Any, Dict, Optional
import requests
from .base import DNSProvider


class CloudflareProvider(DNSProvider):
    def __init__(self, api_token: str, zone_id: str) -> None:
        self.api_token = api_token
        self.zone_id = zone_id
        self.base_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def provider_name(self) -> str:
        return "cloudflare"

    def _find_record(self, name: str, record_type: str) -> Optional[Dict[str, Any]]:
        params = {"type": record_type, "name": name, "page": 1, "per_page": 100}
        r = requests.get(f"{self.base_url}/dns_records", headers=self.headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("success") and data.get("result"):
            return data["result"][0]
        return None

    def update_record(self, name: str, record_type: str, value: str, ttl: int) -> Dict[str, Any]:
        record = self._find_record(name, record_type)
        payload = {
            "type": record_type,
            "name": name,
            "content": value,
            "ttl": ttl,
            "proxied": False,
        }
        if record:
            rec_id = record["id"]
            r = requests.put(f"{self.base_url}/dns_records/{rec_id}", headers=self.headers, json=payload, timeout=10)
        else:
            r = requests.post(f"{self.base_url}/dns_records", headers=self.headers, json=payload, timeout=10)
        r.raise_for_status()
        resp = r.json()
        return {
            "status": "success" if resp.get("success") else "error",
            "provider": self.provider_name(),
            "name": name,
            "type": record_type,
            "value": value,
            "ttl": ttl,
            "result": resp.get("result"),
            "errors": resp.get("errors"),
        }

