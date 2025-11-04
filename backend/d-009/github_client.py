import base64
import json
import time
from typing import Any, Dict, List, Optional

import requests
import logging

try:
    import jwt  # PyJWT
except Exception:
    jwt = None

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, token: Optional[str] = None, app_id: Optional[str] = None, private_key_pem: Optional[str] = None):
        self._base = "https://api.github.com"
        self._token = token
        self.app_id = app_id
        self.private_key_pem = private_key_pem
        self.installation_id: Optional[int] = None
        self._installation_token: Optional[str] = None
        self._installation_token_expiry = 0
        self.is_app_authenticated = bool(app_id and private_key_pem)
        self.app_slug = None

    def set_installation(self, installation_id: Optional[int]):
        self.installation_id = installation_id

    def _headers(self, accept_preview: Optional[str] = None) -> Dict[str, str]:
        token = self._resolve_token()
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}" if token else None,
            "User-Agent": "depbot-renovate-risk-bot/1.0"
        }
        if accept_preview:
            headers["Accept"] = accept_preview
        return {k: v for k, v in headers.items() if v is not None}

    def _resolve_token(self) -> Optional[str]:
        if self.is_app_authenticated:
            return self._get_installation_token()
        return self._token

    def _get_installation_token(self) -> Optional[str]:
        if not self.is_app_authenticated:
            return self._token
        if not self.installation_id:
            return self._token  # fallback to PAT if provided
        now = int(time.time())
        if self._installation_token and now < self._installation_token_expiry - 60:
            return self._installation_token
        if not jwt:
            raise RuntimeError("PyJWT is required for GitHub App auth")
        bearer = self._generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "depbot-renovate-risk-bot/1.0",
        }
        url = f"{self._base}/app/installations/{self.installation_id}/access_tokens"
        resp = requests.post(url, headers=headers)
        if resp.status_code >= 300:
            raise RuntimeError(f"Failed to get installation token: {resp.status_code} {resp.text}")
        data = resp.json()
        self._installation_token = data.get("token")
        expires_at = data.get("expires_at")
        # Simplistic expiry parse: 2023-07-26T12:34:56Z -> epoch
        try:
            from datetime import datetime
            self._installation_token_expiry = int(datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").timestamp())
        except Exception:
            self._installation_token_expiry = now + 3000
        # fetch app slug once
        if not self.app_slug:
            self.app_slug = self.get_app_slug(bearer)
        return self._installation_token

    def get_app_slug(self, app_jwt: str) -> Optional[str]:
        resp = requests.get(f"{self._base}/app", headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "depbot-renovate-risk-bot/1.0",
        })
        if resp.ok:
            return resp.json().get("slug")
        return None

    def _generate_app_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 9 * 60,
            "iss": self.app_id,
        }
        return jwt.encode(payload, self.private_key_pem, algorithm="RS256")

    def _req(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{self._base}{path}"
        headers = kwargs.pop("headers", {})
        headers = {**self._headers(), **headers}
        resp = requests.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            logger.warning("GitHub rate-limited: %s", resp.text)
        return resp

    def list_pull_files(self, owner: str, repo: str, number: int) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page = 1
        while True:
            resp = self._req("GET", f"/repos/{owner}/{repo}/pulls/{number}/files", params={"per_page": 100, "page": page})
            if resp.status_code >= 300:
                raise RuntimeError(f"list_pull_files failed: {resp.status_code} {resp.text}")
            batch = resp.json()
            items.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return items

    def list_issue_comments(self, owner: str, repo: str, number: int) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page = 1
        while True:
            resp = self._req("GET", f"/repos/{owner}/{repo}/issues/{number}/comments", params={"per_page": 100, "page": page})
            if resp.status_code >= 300:
                raise RuntimeError(f"list_issue_comments failed: {resp.status_code} {resp.text}")
            batch = resp.json()
            items.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return items

    def create_issue_comment(self, owner: str, repo: str, number: int, body: str) -> Dict[str, Any]:
        resp = self._req("POST", f"/repos/{owner}/{repo}/issues/{number}/comments", json={"body": body})
        if resp.status_code >= 300:
            raise RuntimeError(f"create_comment failed: {resp.status_code} {resp.text}")
        return resp.json()

    def update_comment(self, owner: str, repo: str, comment_id: int, body: str) -> Dict[str, Any]:
        resp = self._req("PATCH", f"/repos/{owner}/{repo}/issues/comments/{comment_id}", json={"body": body})
        if resp.status_code >= 300:
            raise RuntimeError(f"update_comment failed: {resp.status_code} {resp.text}")
        return resp.json()

    def add_labels(self, owner: str, repo: str, number: int, labels: List[str]) -> List[Dict[str, Any]]:
        resp = self._req("POST", f"/repos/{owner}/{repo}/issues/{number}/labels", json={"labels": labels})
        if resp.status_code >= 300:
            raise RuntimeError(f"add_labels failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_issue_labels(self, owner: str, repo: str, number: int) -> List[Dict[str, Any]]:
        resp = self._req("GET", f"/repos/{owner}/{repo}/issues/{number}/labels")
        if resp.status_code >= 300:
            raise RuntimeError(f"get_issue_labels failed: {resp.status_code} {resp.text}")
        return resp.json()

    def combined_status_success(self, owner: str, repo: str, sha: str) -> bool:
        # Combined Statuses API (for legacy statuses)
        resp = self._req("GET", f"/repos/{owner}/{repo}/commits/{sha}/status")
        if resp.status_code >= 300:
            return False
        state = resp.json().get("state")  # success, failure, pending
        if state != "success":
            return False
        # Also check Check Runs API
        resp2 = self._req("GET", f"/repos/{owner}/{repo}/commits/{sha}/check-runs", headers={"Accept": "application/vnd.github+json"})
        if resp2.status_code == 200:
            data = resp2.json() or {}
            runs = data.get("check_runs", [])
            if runs:
                return all(run.get("conclusion") in ("success", "neutral", "skipped") for run in runs if run.get("status") == "completed")
        return True

    def merge_pr(self, owner: str, repo: str, number: int, method: str = "squash", commit_title: Optional[str] = None) -> Dict[str, Any]:
        payload = {"merge_method": method}
        if commit_title:
            payload["commit_title"] = commit_title
        resp = self._req("PUT", f"/repos/{owner}/{repo}/pulls/{number}/merge", json=payload)
        if resp.status_code >= 300:
            raise RuntimeError(f"merge_pr failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_pull_request(self, owner: str, repo: str, number: int) -> Dict[str, Any]:
        resp = self._req("GET", f"/repos/{owner}/{repo}/pulls/{number}")
        if resp.status_code >= 300:
            raise RuntimeError(f"get_pull_request failed: {resp.status_code} {resp.text}")
        return resp.json()

