import hashlib
import json
import os
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from requests.auth import HTTPBasicAuth

ACCEPT_MANIFEST = ', '.join([
    'application/vnd.oci.image.index.v1+json',
    'application/vnd.docker.distribution.manifest.list.v2+json',
    'application/vnd.oci.image.manifest.v1+json',
    'application/vnd.docker.distribution.manifest.v2+json'
])

class RegistryError(Exception):
    def __init__(self, message: str, status: int = None, details=None):
        super().__init__(message)
        self.status = status
        self.details = details

class RegistryClient:
    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None, verify_tls: bool = True, timeout: int = 30, extra_headers: Optional[Dict[str, str]] = None):
        if not base_url.startswith('http://') and not base_url.startswith('https://'):
            raise ValueError('Registry base_url must include scheme (http/https)')
        self.base_url = base_url.rstrip('/') + '/'
        self.session = requests.Session()
        self.session.verify = verify_tls
        self.timeout = timeout
        self.session.headers.update({'User-Agent': 'artifact-promoter/1.0'})
        self.extra_headers = extra_headers or {}
        if username:
            self.session.auth = HTTPBasicAuth(username, password or '')

    def _url(self, path: str) -> str:
        if path.startswith('http://') or path.startswith('https://'):
            return path
        return urljoin(self.base_url, path.lstrip('/'))

    def _request(self, method: str, path: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, str]] = None, data=None, stream: bool = False, allow_redirects: bool = True):
        url = self._url(path)
        hdrs = {}
        hdrs.update(self.extra_headers)
        if headers:
            hdrs.update(headers)
        resp = self.session.request(method=method, url=url, headers=hdrs, params=params, data=data, stream=stream, timeout=self.timeout, allow_redirects=allow_redirects)
        return resp

    def manifest_exists(self, repository: str, reference: str) -> bool:
        path = f'/v2/{repository}/manifests/{reference}'
        resp = self._request('HEAD', path, headers={'Accept': ACCEPT_MANIFEST})
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        raise RegistryError(f'HEAD manifest failed: {resp.status_code} {resp.text}', resp.status_code)

    def get_manifest(self, repository: str, reference: str) -> Tuple[bytes, str, Optional[str]]:
        path = f'/v2/{repository}/manifests/{reference}'
        resp = self._request('GET', path, headers={'Accept': ACCEPT_MANIFEST})
        if resp.status_code != 200:
            raise RegistryError(f'GET manifest failed: {resp.status_code} {resp.text}', resp.status_code)
        content_type = resp.headers.get('Content-Type')
        digest = resp.headers.get('Docker-Content-Digest')
        content = resp.content
        return content, content_type, digest

    def put_manifest(self, repository: str, reference: str, manifest_bytes: bytes, content_type: str) -> str:
        path = f'/v2/{repository}/manifests/{reference}'
        resp = self._request('PUT', path, headers={'Content-Type': content_type}, data=manifest_bytes)
        if resp.status_code not in (201, 202):
            raise RegistryError(f'PUT manifest failed: {resp.status_code} {resp.text}', resp.status_code)
        return resp.headers.get('Docker-Content-Digest')

    def blob_exists(self, repository: str, digest: str) -> bool:
        path = f'/v2/{repository}/blobs/{digest}'
        resp = self._request('HEAD', path)
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        raise RegistryError(f'HEAD blob failed: {resp.status_code} {resp.text}', resp.status_code)

    def download_blob_to_file(self, repository: str, digest: str, file_path: str) -> int:
        path = f'/v2/{repository}/blobs/{digest}'
        resp = self._request('GET', path, stream=True)
        if resp.status_code != 200:
            raise RegistryError(f'GET blob failed: {resp.status_code} {resp.text}', resp.status_code)
        hasher = hashlib.sha256()
        total = 0
        with open(file_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                hasher.update(chunk)
                total += len(chunk)
        # Verify digest if sha256
        algo, _, expected = digest.partition(':')
        if algo == 'sha256':
            if hasher.hexdigest() != expected:
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                raise RegistryError('Downloaded blob digest mismatch')
        return total

    def _absolute_location(self, loc: str) -> str:
        if loc.startswith('http://') or loc.startswith('https://'):
            return loc
        # Some registries return relative paths
        return urljoin(self.base_url, loc.lstrip('/'))

    def upload_blob(self, repository: str, digest: str, file_path: str, size: Optional[int] = None) -> None:
        # Initiate upload
        init_path = f'/v2/{repository}/blobs/uploads/'
        init_resp = self._request('POST', init_path)
        if init_resp.status_code not in (202,):
            raise RegistryError(f'Initiate upload failed: {init_resp.status_code} {init_resp.text}', init_resp.status_code)
        upload_url = self._absolute_location(init_resp.headers.get('Location') or init_resp.headers.get('Docker-Upload-Location') or '')
        if not upload_url:
            raise RegistryError('Upload initiation missing Location header')

        # Monolithic upload with digest
        params = {'digest': digest}
        headers = {'Content-Type': 'application/octet-stream'}
        if size is None:
            size = os.path.getsize(file_path)
        headers['Content-Length'] = str(size)
        with open(file_path, 'rb') as f:
            put_resp = self.session.put(upload_url, params=params, headers=headers, data=f, timeout=self.timeout)
        if put_resp.status_code not in (201,):
            # Try fallback: PATCH then PUT finalize
            with open(file_path, 'rb') as f:
                patch_headers = {'Content-Type': 'application/octet-stream'}
                patch_resp = self.session.patch(upload_url, headers=patch_headers, data=f, timeout=self.timeout)
            if patch_resp.status_code not in (202,):
                raise RegistryError(f'PATCH upload failed: {patch_resp.status_code} {patch_resp.text}', patch_resp.status_code)
            finalize_url = patch_resp.headers.get('Location')
            finalize_url = self._absolute_location(finalize_url or upload_url)
            fin_resp = self.session.put(finalize_url, params={'digest': digest}, headers={}, timeout=self.timeout)
            if fin_resp.status_code not in (201,):
                raise RegistryError(f'Finalize upload failed: {fin_resp.status_code} {fin_resp.text}', fin_resp.status_code)

    # Optional utility for completeness; not used directly
    def delete_manifest(self, repository: str, reference: str) -> None:
        path = f'/v2/{repository}/manifests/{reference}'
        resp = self._request('DELETE', path)
        if resp.status_code not in (202,):
            raise RegistryError(f'DELETE manifest failed: {resp.status_code} {resp.text}', resp.status_code)

