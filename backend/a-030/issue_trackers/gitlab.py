from __future__ import annotations
import requests
from typing import Any, Dict, List, Optional

from .base import IssueTracker, IssueTrackerError


class GitLabIssueTracker(IssueTracker):
    def __init__(self, token: str, project_id: str, base_url: str = "https://gitlab.com"):
        if not token or not project_id:
            raise ValueError("GitLab token and project_id are required")
        self.token = token
        self.project_id = project_id
        self.api = base_url.rstrip("/") + "/api/v4"
        self.session = requests.Session()
        self.session.headers.update({
            "Private-Token": self.token,
            "User-Agent": "gap-issue-bot/1.0",
        })

    def create_issue(self, title: str, body: str, labels: Optional[List[str]] = None, assignees: Optional[List[str]] = None) -> Dict[str, Any]:
        url = f"{self.api}/projects/{self.project_id}/issues"
        payload: Dict[str, Any] = {"title": title, "description": body}
        if labels:
            payload["labels"] = ",".join(labels)
        # GitLab assignees usually require numeric user IDs; skip if not provided as IDs
        if assignees and all(isinstance(a, int) for a in assignees):
            payload["assignee_ids"] = assignees
        r = self.session.post(url, data=payload, timeout=30)
        if r.status_code >= 300:
            raise IssueTrackerError(f"GitLab create issue failed: {r.status_code} {r.text}")
        data = r.json()
        return {"issue_id": data.get("iid"), "issue_url": data.get("web_url")}

    def find_issue_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.api}/projects/{self.project_id}/issues"
        r = self.session.get(url, params={"search": external_id, "in": "title,description", "per_page": 1}, timeout=30)
        if r.status_code >= 300:
            return None
        items = r.json()
        if not items:
            return None
        first = items[0]
        return {"issue_id": first.get("iid"), "issue_url": first.get("web_url")}

