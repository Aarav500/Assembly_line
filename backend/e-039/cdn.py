import logging
import requests
from urllib.parse import urljoin, quote

logger = logging.getLogger(__name__)

class CDNProvider:
    def purge(self, paths):
        raise NotImplementedError

class NoopCDN(CDNProvider):
    def __init__(self, base_url=""):
        self.base_url = base_url

    def purge(self, paths):
        logger.info("[CDN Noop] Skipping purge for %d paths", len(paths))
        # Return a stable response shape
        return {
            "provider": "noop",
            "purged": [urljoin(self.base_url, p) if self.base_url else p for p in paths],
            "status": "ok"
        }

class CloudflareCDN(CDNProvider):
    def __init__(self, api_token, zone_id, base_url):
        self.api_token = api_token
        self.zone_id = zone_id
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.endpoint = f"https://api.cloudflare.com/client/v4/zones/{self.zone_id}/purge_cache"

    def purge(self, paths):
        if not self.base_url:
            raise ValueError("CDN_BASE_URL is required for Cloudflare purge.")
        files = [urljoin(self.base_url + '/', p.lstrip('/')) for p in paths]
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        payload = {"files": files}
        resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=30)
        try:
            data = resp.json()
        except Exception:
            data = {"error": resp.text}
        if not resp.ok:
            logger.error("Cloudflare purge failed: %s", data)
        else:
            logger.info("Cloudflare purge success for %d items", len(files))
        return {"provider": "cloudflare", "status_code": resp.status_code, "response": data, "files": files}

class FastlyCDN(CDNProvider):
    def __init__(self, api_key, service_id, base_url):
        self.api_key = api_key
        self.service_id = service_id
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.api_base = "https://api.fastly.com"

    def purge(self, paths):
        if not self.base_url:
            raise ValueError("CDN_BASE_URL is required for Fastly purge.")
        results = []
        headers = {
            "Fastly-Key": self.api_key,
            "Accept": "application/json"
        }
        for p in paths:
            url = urljoin(self.base_url + '/', p.lstrip('/'))
            target = f"{self.api_base}/purge/{quote(url, safe='')}"
            try:
                resp = requests.post(target, headers=headers, timeout=30)
                try:
                    data = resp.json()
                except Exception:
                    data = {"error": resp.text}
                results.append({"url": url, "status_code": resp.status_code, "response": data})
            except Exception as e:
                results.append({"url": url, "error": str(e)})
        return {"provider": "fastly", "results": results}


def get_cdn_provider(cfg):
    provider = (cfg.CDN_PROVIDER or "noop").lower()
    if provider == "cloudflare":
        return CloudflareCDN(cfg.CF_API_TOKEN, cfg.CF_ZONE_ID, cfg.CDN_BASE_URL)
    if provider == "fastly":
        return FastlyCDN(cfg.FASTLY_API_KEY, cfg.FASTLY_SERVICE_ID, cfg.CDN_BASE_URL)
    return NoopCDN(cfg.CDN_BASE_URL)

