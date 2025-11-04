import json
import os
import time
from typing import Iterable, List, Optional
import requests

try:
    import boto3
except Exception:  # pragma: no cover
    boto3 = None  # type: ignore


class PurgeError(Exception):
    pass


class BasePurger:
    def purge_all(self, soft: bool = True) -> dict:
        raise NotImplementedError

    def purge_paths(self, paths: Iterable[str], soft: bool = True) -> dict:
        raise NotImplementedError

    def purge_tags(self, tags: Iterable[str], soft: bool = True) -> dict:
        raise NotImplementedError

    # Alias for systems where keys == tags
    def purge_keys(self, keys: Iterable[str], soft: bool = True) -> dict:
        return self.purge_tags(keys, soft=soft)


class CloudflarePurger(BasePurger):
    def __init__(self, api_token: str, zone_id: str, site_url: str = ""):
        self.api_token = api_token
        self.zone_id = zone_id
        self.site_url = site_url.rstrip("/") if site_url else ""
        self.base = f"https://api.cloudflare.com/client/v4/zones/{self.zone_id}/purge_cache"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def purge_all(self, soft: bool = True) -> dict:
        r = requests.post(self.base, headers=self.headers, data=json.dumps({"purge_everything": True}), timeout=30)
        if r.status_code >= 300:
            raise PurgeError(f"Cloudflare purge_all failed: {r.status_code} {r.text}")
        return r.json()

    def purge_paths(self, paths: Iterable[str], soft: bool = True) -> dict:
        files: List[str] = []
        for p in paths:
            s = str(p).strip()
            if not s:
                continue
            if s.startswith("http://") or s.startswith("https://"):
                files.append(s)
            elif self.site_url:
                files.append(f"{self.site_url}{s if s.startswith('/') else '/' + s}")
            else:
                raise PurgeError("Cloudflare purge_paths requires absolute URLs or CLOUDFLARE_SITE_URL")
        payload = {"files": files}
        r = requests.post(self.base, headers=self.headers, data=json.dumps(payload), timeout=30)
        if r.status_code >= 300:
            raise PurgeError(f"Cloudflare purge_paths failed: {r.status_code} {r.text}")
        return r.json()

    def purge_tags(self, tags: Iterable[str], soft: bool = True) -> dict:
        tags_list = [t for t in tags if t]
        if not tags_list:
            return {"skipped": True, "reason": "no tags"}
        payload = {"tags": tags_list}
        r = requests.post(self.base, headers=self.headers, data=json.dumps(payload), timeout=30)
        if r.status_code >= 300:
            raise PurgeError(f"Cloudflare purge_tags failed: {r.status_code} {r.text}")
        return r.json()


class FastlyPurger(BasePurger):
    def __init__(self, api_token: str, service_id: str):
        self.api_token = api_token
        self.service_id = service_id
        self.base = "https://api.fastly.com"
        self.headers = {
            "Fastly-Key": self.api_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def purge_all(self, soft: bool = True) -> dict:
        url = f"{self.base}/service/{self.service_id}/purge_all"
        headers = dict(self.headers)
        if soft:
            headers["Fastly-Soft-Purge"] = "1"
        r = requests.post(url, headers=headers, timeout=30)
        if r.status_code >= 300:
            raise PurgeError(f"Fastly purge_all failed: {r.status_code} {r.text}")
        return r.json()

    def purge_paths(self, paths: Iterable[str], soft: bool = True) -> dict:
        # Fastly recommends purging by surrogate keys; path PURGE is edge-facing and requires host. Using keys is better.
        return {"warning": "Path purge is not recommended for Fastly via API. Use purge_keys instead.", "skipped": True}

    def purge_tags(self, tags: Iterable[str], soft: bool = True) -> dict:
        keys = [t for t in tags if t]
        if not keys:
            return {"skipped": True, "reason": "no keys"}
        url = f"{self.base}/service/{self.service_id}/purge"
        headers = dict(self.headers)
        if soft:
            headers["Fastly-Soft-Purge"] = "1"
        payload = {"surrogate_keys": keys}
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        if r.status_code >= 300:
            raise PurgeError(f"Fastly purge_keys failed: {r.status_code} {r.text}")
        return r.json()

    def purge_keys(self, keys: Iterable[str], soft: bool = True) -> dict:
        return self.purge_tags(keys, soft=soft)


class CloudFrontPurger(BasePurger):
    def __init__(self, distribution_id: str, region_name: Optional[str] = None):
        if boto3 is None:
            raise PurgeError("boto3 is required for CloudFront purging")
        self.distribution_id = distribution_id
        session = boto3.session.Session(region_name=region_name or os.getenv("AWS_REGION", "us-east-1"))
        self.cf = session.client("cloudfront")

    def _normalize_paths(self, paths: Iterable[str]) -> List[str]:
        norm: List[str] = []
        for p in paths:
            s = str(p or "").strip()
            if not s:
                continue
            # If it's a URL, extract path
            if s.startswith("http://") or s.startswith("https://"):
                try:
                    from urllib.parse import urlparse
                    s = urlparse(s).path or "/"
                except Exception:
                    s = "/"
            if not s.startswith("/"):
                s = "/" + s
            norm.append(s)
        # CloudFront requires unique paths
        return sorted(set(norm))

    def purge_all(self, soft: bool = True) -> dict:
        return self.purge_paths(["/*"], soft=soft)

    def purge_paths(self, paths: Iterable[str], soft: bool = True) -> dict:
        items = self._normalize_paths(paths)
        if not items:
            return {"skipped": True, "reason": "no paths"}
        # CloudFront invalidation supports up to 1000 paths per request
        if len(items) > 1000:
            items = items[:1000]
        caller_ref = f"purge-{int(time.time())}"
        res = self.cf.create_invalidation(
            DistributionId=self.distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": len(items), "Items": items},
                "CallerReference": caller_ref,
            },
        )
        return res

    def purge_tags(self, tags: Iterable[str], soft: bool = True) -> dict:
        # CloudFront has no tag purge; advise using path invalidations.
        return {"warning": "CloudFront does not support tag-based purging.", "skipped": True}


def get_purger_from_env() -> BasePurger:
    provider = (os.getenv("CDN_PROVIDER") or "").lower()
    if provider == "cloudflare":
        token = os.getenv("CLOUDFLARE_API_TOKEN", "")
        zone = os.getenv("CLOUDFLARE_ZONE_ID", "")
        site = os.getenv("CLOUDFLARE_SITE_URL", "")
        if not token or not zone:
            raise PurgeError("Missing Cloudflare credentials (CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID)")
        return CloudflarePurger(token, zone, site)
    elif provider == "fastly":
        token = os.getenv("FASTLY_API_TOKEN", "")
        service = os.getenv("FASTLY_SERVICE_ID", "")
        if not token or not service:
            raise PurgeError("Missing Fastly credentials (FASTLY_API_TOKEN, FASTLY_SERVICE_ID)")
        return FastlyPurger(token, service)
    elif provider == "cloudfront":
        dist = os.getenv("CLOUDFRONT_DISTRIBUTION_ID", "")
        region = os.getenv("AWS_REGION", None)
        if not dist:
            raise PurgeError("Missing CloudFront distribution id (CLOUDFRONT_DISTRIBUTION_ID)")
        return CloudFrontPurger(dist, region)
    else:
        raise PurgeError("Unknown or unset CDN_PROVIDER. Expected one of: cloudflare|fastly|cloudfront")

