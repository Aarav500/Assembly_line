from __future__ import annotations
import requests
from typing import Any, Dict, List, Optional

from .base import IssueTracker, IssueTrackerError


class GitHubIssueTracker(IssueTracker):
    def __init__(self, token: str, repo: str):
        if not token or not repo or "/" not in repo:
            raise ValueError("GitHub token and repo (owner/repo) are required")
        self.token = token
        self.owner, self.repo = repo.split("/", 1)
        self.api = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gap-issue-bot/1.0",
        })

    def create_issue(self, title: str, body: str, labels: Optional[List[str]] = None, assignees: Optional[List[str]] = None) -> Dict[str, Any]:
        url = f"{self.api}/repos/{self.owner}/{self.repo}/issues"
        payload: Dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees
        r = self.session.post(url, json=payload, timeout=30)
        if r.status_code >= 300:
            raise IssueTrackerError(f"GitHub create issue failed: {r.status_code} {r.text}")
        data = r.json()
        return {"issue_id": data.get("number"), "issue_url": data.get("html_url")}

    def find_issue_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        # Use GitHub search API to find existing issues containing the external_id in title or body
        # Requires repo scope and search visibility per token permissions
        q = f"repo:{self.owner}/{self.repo} in:title,body {external_id}"
        url = f"{self.api}/search/issues"
        r = self.session.get(url, params={"q": q, "per_page": 1}, timeout=30)
        if r.status_code >= 300:
            return None
        items = r.json().get("items", [])
        if not items:
            return None
        first = items[0]
        return {"issue_id": first.get("number"), "issue_url": first.get("html_url")}

