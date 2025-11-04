from __future__ import annotations
import time
from typing import Dict, List, Optional, Tuple
import requests
from packaging.version import Version, InvalidVersion
from packaging.utils import canonicalize_name


DEFAULT_TIMEOUT = 10


class PyPIClient:
    def __init__(self, base_url: str = "https://pypi.org/pypi", timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.timeout = timeout
        self._cache_project: Dict[str, dict] = {}
        self._cache_release: Dict[Tuple[str, str], dict] = {}
        self._last_request_ts = 0.0
        self._min_interval = 0.05  # be nice to PyPI

    def _throttle(self):
        now = time.time()
        delta = now - self._last_request_ts
        if delta < self._min_interval:
            time.sleep(self._min_interval - delta)
        self._last_request_ts = time.time()

    def _get(self, url: str) -> dict:
        self._throttle()
        r = self.session.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_project(self, name: str) -> dict:
        key = canonicalize_name(name)
        if key in self._cache_project:
            return self._cache_project[key]
        url = f"{self.base_url}/{name}/json"
        data = self._get(url)
        self._cache_project[key] = data
        return data

    def get_release(self, name: str, version: str) -> dict:
        key = (canonicalize_name(name), str(version))
        if key in self._cache_release:
            return self._cache_release[key]
        url = f"{self.base_url}/{name}/{version}/json"
        data = self._get(url)
        self._cache_release[key] = data
        return data

    def get_all_versions(self, name: str, include_prereleases: bool = False) -> List[Version]:
        try:
            data = self.get_project(name)
        except Exception:
            return []
        releases = data.get("releases") or {}
        versions: List[Version] = []
        for ver_str, files in releases.items():
            try:
                v = Version(ver_str)
            except InvalidVersion:
                continue
            if not include_prereleases and v.is_prerelease:
                continue
            if not files:
                continue
            # Exclude fully yanked releases (all files yanked)
            if all(bool(f.get("yanked")) for f in files if isinstance(f, dict)):
                continue
            versions.append(v)
        versions.sort()
        return versions

    def get_release_metadata(self, name: str, version: Version) -> dict:
        try:
            return self.get_release(name, str(version))
        except Exception as e:
            return {"error": str(e), "name": name, "version": str(version)}

