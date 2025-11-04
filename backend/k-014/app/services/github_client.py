import os
import typing as t
import requests
from flask import current_app


class GitHubClient:
    def __init__(self, token: t.Optional[str] = None, timeout: float = 20.0):
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github+json"})
        token = token or os.environ.get("GITHUB_TOKEN")
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{self.base_url}{path}"
        r = self.session.get(url, params=params, timeout=self.timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub API error {r.status_code}: {r.text}")
        return r.json()

    def get_repo(self, owner: str, repo: str) -> dict:
        return self._get(f"/repos/{owner}/{repo}")

    def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> list[dict]:
        return self._get(f"/repos/{owner}/{repo}/pulls", params={"state": state, "per_page": 100})

    def get_pull_request(self, owner: str, repo: str, number: int) -> dict:
        return self._get(f"/repos/{owner}/{repo}/pulls/{number}")

    def get_pull_request_files(self, owner: str, repo: str, number: int) -> list[dict]:
        files = []
        page = 1
        while True:
            chunk = self._get(
                f"/repos/{owner}/{repo}/pulls/{number}/files", params={"per_page": 100, "page": page}
            )
            files.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        return files

    def get_pull_request_commits(self, owner: str, repo: str, number: int) -> list[dict]:
        commits = []
        page = 1
        while True:
            chunk = self._get(
                f"/repos/{owner}/{repo}/pulls/{number}/commits", params={"per_page": 100, "page": page}
            )
            commits.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        return commits


def get_client() -> GitHubClient:
    return GitHubClient(token=current_app.config.get("GITHUB_TOKEN"), timeout=current_app.config.get("HTTP_TIMEOUT", 20.0))

