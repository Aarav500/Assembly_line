import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin
from typing import Dict, List, Optional, Tuple


MANIFEST_V2 = 'application/vnd.docker.distribution.manifest.v2+json'


class RegistryClient:
    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None, verify_ssl: bool = True):
        if not base_url:
            raise ValueError("REGISTRY_URL must be configured")
        self.base_url = base_url.rstrip('/') + '/'
        self.session = requests.Session()
        self.session.verify = verify_ssl
        if username:
            self.session.auth = HTTPBasicAuth(username, password or '')
        self.session.headers.update({'User-Agent': 'LifecyclePolicyService/1.0'})

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip('/'))

    def ping(self) -> bool:
        try:
            r = self.session.get(self._url('/v2/'))
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_repositories(self, n: int = 1000) -> List[str]:
        repos = []
        url = self._url(f"/v2/_catalog?n={n}")
        while True:
            r = self.session.get(url)
            r.raise_for_status()
            data = r.json()
            repos.extend(data.get('repositories', []) )
            link = r.headers.get('Link')
            if link and 'rel="next"' in link:
                # Extract next url from Link header: <url>; rel="next"
                start = link.find('<')
                end = link.find('>')
                if start != -1 and end != -1 and end > start:
                    url = link[start+1:end]
                    continue
            break
        return sorted(set(repos))

    def list_tags(self, repository: str) -> List[str]:
        r = self.session.get(self._url(f"/v2/{repository}/tags/list"))
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json().get('tags', []) or []

    def get_manifest(self, repository: str, reference: str) -> Tuple[dict, Optional[str]]:
        headers = {'Accept': MANIFEST_V2}
        r = self.session.get(self._url(f"/v2/{repository}/manifests/{reference}"), headers=headers)
        r.raise_for_status()
        digest = r.headers.get('Docker-Content-Digest')
        return r.json(), digest

    def head_manifest_digest(self, repository: str, reference: str) -> Optional[str]:
        headers = {'Accept': MANIFEST_V2}
        r = self.session.head(self._url(f"/v2/{repository}/manifests/{reference}"), headers=headers)
        if r.status_code == 200:
            return r.headers.get('Docker-Content-Digest')
        # fallback to GET
        try:
            _, digest = self.get_manifest(repository, reference)
            return digest
        except Exception:
            return None

    def get_config_blob(self, repository: str, digest: str) -> dict:
        r = self.session.get(self._url(f"/v2/{repository}/blobs/{digest}"))
        r.raise_for_status()
        return r.json()

    def delete_manifest(self, repository: str, digest: str) -> bool:
        r = self.session.delete(self._url(f"/v2/{repository}/manifests/{digest}"))
        # 202 Accepted on success
        if r.status_code in (202, 200):
            return True
        # some registries return 404 if already deleted
        if r.status_code == 404:
            return True
        r.raise_for_status()
        return True

    def tag_metadata(self, repository: str, tag: str) -> dict:
        # Get manifest and find config blob digest for created time
        manifest, digest = self.get_manifest(repository, tag)
        config = manifest.get('config') or {}
        cfg_digest = config.get('digest')
        created = None
        if cfg_digest:
            try:
                cfg = self.get_config_blob(repository, cfg_digest)
                created = cfg.get('created')
            except Exception:
                created = None
        return {
            'tag': tag,
            'manifest_digest': digest,
            'config_digest': cfg_digest,
            'created': created,
        }

