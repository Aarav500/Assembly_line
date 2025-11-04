import requests
from typing import Optional
from .base import BaseDNSProvider


class CloudflareDNSProvider(BaseDNSProvider):
    def __init__(self, api_token: str) -> None:
        self.api_token = api_token
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        })

    def _zone_for_name(self, fqdn: str) -> str:
        parts = fqdn.rstrip('.').split('.')
        if len(parts) < 2:
            raise ValueError(f"Invalid FQDN: {fqdn}")
        return ".".join(parts[-2:])

    def _get_zone_id(self, zone_name: str) -> Optional[str]:
        resp = self.session.get(f"{self.base_url}/zones", params={"name": zone_name})
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result", [])
        if result:
            return result[0]["id"]
        return None

    def _find_record(self, zone_id: str, name: str, rtype: str = "TXT", content: Optional[str] = None) -> Optional[dict]:
        params = {"type": rtype, "name": name}
        if content:
            params["content"] = content
        resp = self.session.get(f"{self.base_url}/zones/{zone_id}/dns_records", params=params)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("result", [])
        return results[0] if results else None

    def ensure_txt_record(self, name: str, value: str, ttl: int = 60) -> None:
        zone_name = self._zone_for_name(name)
        zone_id = self._get_zone_id(zone_name)
        if not zone_id:
            raise RuntimeError(f"Cloudflare zone not found for {zone_name}")

        existing = self._find_record(zone_id, name, "TXT", value)
        if existing:
            # Already present with same content
            return

        # If record with name exists but different content, create another
        payload = {"type": "TXT", "name": name, "content": value, "ttl": ttl}
        resp = self.session.post(f"{self.base_url}/zones/{zone_id}/dns_records", json=payload)
        resp.raise_for_status()
        ok = resp.json().get("success", False)
        if not ok:
            raise RuntimeError(f"Failed to create TXT record {name}")

    def delete_txt_record(self, name: str, value: str) -> None:
        zone_name = self._zone_for_name(name)
        zone_id = self._get_zone_id(zone_name)
        if not zone_id:
            return
        rec = self._find_record(zone_id, name, "TXT", value)
        if not rec:
            return
        rec_id = rec["id"]
        resp = self.session.delete(f"{self.base_url}/zones/{zone_id}/dns_records/{rec_id}")
        resp.raise_for_status()

