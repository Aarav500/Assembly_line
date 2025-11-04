import base64
import json
import os
from typing import Optional, Dict, Any
import requests

from config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BASE_BRANCH, GITHUB_DESIRED_PATH


class GitHubClient:
    def __init__(self):
        if not GITHUB_REPO:
            raise RuntimeError('GITHUB_REPO is not configured')
        if not GITHUB_TOKEN:
            raise RuntimeError('GITHUB_TOKEN is not configured')
        self.repo = GITHUB_REPO
        self.base_branch = GITHUB_BASE_BRANCH
        self.token = GITHUB_TOKEN
        self.api = 'https://api.github.com'
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'drift-alerts-bot'
        })

    def desired_path(self) -> str:
        return GITHUB_DESIRED_PATH

    def _repo_url(self, path: str) -> str:
        return f"{self.api}/repos/{self.repo}{path}"

    def get_file(self, path: str, ref: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if ref:
            params['ref'] = ref
        r = self._session.get(self._repo_url(f"/contents/{path}"), params=params)
        if r.status_code != 200:
            raise RuntimeError(f"Failed to get file {path}: {r.status_code} {r.text}")
        return r.json()

    def get_file_text(self, path: str, ref: Optional[str] = None) -> str:
        data = self.get_file(path, ref)
        if 'content' not in data:
            raise RuntimeError(f"Unexpected response for contents of {path}")
        content_b64 = data['content']
        if data.get('encoding') == 'base64':
            return base64.b64decode(content_b64).decode('utf-8')
        return content_b64

    def get_ref(self, ref: str) -> Dict[str, Any]:
        r = self._session.get(self._repo_url(f"/git/ref/{ref}"))
        if r.status_code != 200:
            raise RuntimeError(f"Failed to get ref {ref}: {r.status_code} {r.text}")
        return r.json()

    def ensure_branch_from_base(self, new_branch: str, base_branch: Optional[str] = None):
        base_branch = base_branch or self.base_branch
        # Check if branch exists
        r = self._session.get(self._repo_url(f"/git/ref/heads/{new_branch}"))
        if r.status_code == 200:
            return  # already exists
        # Get base SHA
        base = self.get_ref(f"heads/{base_branch}")
        base_sha = base['object']['sha']
        # Create ref
        payload = {'ref': f"refs/heads/{new_branch}", 'sha': base_sha}
        cr = self._session.post(self._repo_url("/git/refs"), json=payload)
        if cr.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create branch {new_branch}: {cr.status_code} {cr.text}")

    def create_or_update_file(self, path: str, content: str, message: str, branch: str):
        # Check if file exists on branch
        params = {'ref': branch}
        url = self._repo_url(f"/contents/{path}")
        r = self._session.get(url, params=params)
        sha = None
        if r.status_code == 200:
            sha = r.json().get('sha')
        elif r.status_code not in (404,):
            raise RuntimeError(f"Failed to check existing file: {r.status_code} {r.text}")

        payload = {
            'message': message,
            'content': base64.b64encode(content.encode('utf-8')).decode('utf-8'),
            'branch': branch
        }
        if sha:
            payload['sha'] = sha
        pr = self._session.put(url, json=payload)
        if pr.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create/update file {path}: {pr.status_code} {pr.text}")
        return pr.json()

    def create_pull_request(self, title: str, body: str, head: str, base: Optional[str] = None) -> Dict[str, Any]:
        base = base or self.base_branch
        payload = {
            'title': title,
            'head': head,
            'base': base,
            'body': body
        }
        r = self._session.post(self._repo_url('/pulls'), json=payload)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create pull request: {r.status_code} {r.text}")
        return r.json()

