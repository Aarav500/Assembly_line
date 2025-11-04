import logging
import os
from typing import Dict, List, Optional, Tuple

import requests

from config import settings

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
        self.base_url = os.getenv("GITHUB_API_BASE", "https://api.github.com")
        if not self.token:
            logger.warning("GITHUB_TOKEN is not set; API calls may be rate-limited or fail")

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str, params: Optional[Dict] = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        self._check(resp)
        return resp

    def post(self, path: str, json: Dict) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = requests.post(url, headers=self._headers(), json=json, timeout=30)
        self._check(resp)
        return resp

    def _check(self, resp: requests.Response):
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            logger.error("GitHub API error %s: %s", resp.status_code, detail)
            resp.raise_for_status()

    # Repository helpers
    def list_tags(self, repo: str, per_page: int = 100) -> List[Dict]:
        tags = []
        page = 1
        while True:
            r = self.get(f"/repos/{repo}/tags", params={"per_page": per_page, "page": page})
            data = r.json()
            if not data:
                break
            tags.extend(data)
            if len(data) < per_page:
                break
            page += 1
        return tags

    def list_releases(self, repo: str, per_page: int = 100) -> List[Dict]:
        releases = []
        page = 1
        while True:
            r = self.get(f"/repos/{repo}/releases", params={"per_page": per_page, "page": page})
            data = r.json()
            if not data:
                break
            releases.extend(data)
            if len(data) < per_page:
                break
            page += 1
        return releases

    def latest_release(self, repo: str) -> Optional[Dict]:
        try:
            r = self.get(f"/repos/{repo}/releases/latest")
            return r.json()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    def get_pull_request_commits(self, repo: str, pr_number: int) -> List[Dict]:
        commits = []
        page = 1
        per_page = 100
        while True:
            r = self.get(f"/repos/{repo}/pulls/{pr_number}/commits", params={"per_page": per_page, "page": page})
            data = r.json()
            if not data:
                break
            commits.extend(data)
            if len(data) < per_page:
                break
            page += 1
        return commits

    def create_release(self, repo: str, tag_name: str, target_commitish: str, name: str, body: str, draft: bool = False, prerelease: bool = False) -> Dict:
        payload = {
            "tag_name": tag_name,
            "target_commitish": target_commitish,
            "name": name,
            "body": body,
            "draft": draft,
            "prerelease": prerelease,
        }
        if settings.DRY_RUN:
            logger.info("DRY_RUN: Would create release: %s", payload)
            return {"dry_run": True, "payload": payload}
        r = self.post(f"/repos/{repo}/releases", json=payload)
        return r.json()

    def get_commit(self, repo: str, sha: str) -> Dict:
        r = self.get(f"/repos/{repo}/commits/{sha}")
        return r.json()


