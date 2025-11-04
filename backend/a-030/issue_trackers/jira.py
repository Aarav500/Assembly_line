from __future__ import annotations
import requests
from typing import Any, Dict, List, Optional
from base64 import b64encode

from .base import IssueTracker, IssueTrackerError


class JiraIssueTracker(IssueTracker):
    def __init__(self, base_url: str, email: str, api_token: str, project_key: str):
        if not base_url or not email or not api_token or not project_key:
            raise ValueError("Jira base_url, email, api_token, and project_key are required")
        self.base_url = base_url.rstrip("/")
        self.project_key = project_key
        self.session = requests.Session()
        token_bytes = f"{email}:{api_token}".encode()
        basic = b64encode(token_bytes).decode()
        self.session.headers.update({
            "Authorization": f"Basic {basic}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "gap-issue-bot/1.0",
        })

    def create_issue(self, title: str, body: str, labels: Optional[List[str]] = None, assignees: Optional[List[str]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/3/issue"
        fields: Dict[str, Any] = {
            "project": {"key": self.project_key},
            "summary": title,
            "issuetype": {"name": "Task"},
            "description": body,
        }
        if labels:
            fields["labels"] = labels
        # Jira cloud expects accountId for assignee
        if assignees and len(assignees) == 1 and isinstance(assignees[0], str) and assignees[0]:
            fields["assignee"] = {"id": assignees[0]}

        r = self.session.post(url, json={"fields": fields}, timeout=30)
        if r.status_code >= 300:
            raise IssueTrackerError(f"Jira create issue failed: {r.status_code} {r.text}")
        data = r.json()
        issue_key = data.get("key")
        browse_url = f"{self.base_url}/browse/{issue_key}" if issue_key else None
        return {"issue_id": issue_key, "issue_url": browse_url}

    def find_issue_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        jql = f'text ~ "{external_id}" AND project = {self.project_key}'
        url = f"{self.base_url}/rest/api/3/search"
        r = self.session.get(url, params={"jql": jql, "maxResults": 1, "fields": "key"}, timeout=30)
        if r.status_code >= 300:
            return None
        issues = r.json().get("issues", [])
        if not issues:
            return None
        first = issues[0]
        key = first.get("key")
        return {"issue_id": key, "issue_url": f"{self.base_url}/browse/{key}"}

