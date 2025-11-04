from __future__ import annotations
import hashlib
from typing import Any, Dict, Optional, List

from config import Config
from issue_trackers.base import IssueTracker
from issue_trackers.github import GitHubIssueTracker
from issue_trackers.gitlab import GitLabIssueTracker
from issue_trackers.jira import JiraIssueTracker
from storage.issue_registry import IssueRegistry


class IssueCreationService:
    def __init__(self, cfg: Config, registry: IssueRegistry):
        self.cfg = cfg
        self.registry = registry
        self.tracker = self._init_tracker(cfg)

    def _init_tracker(self, cfg: Config) -> IssueTracker:
        p = (cfg.tracker_provider or "").lower()
        if p == "github":
            return GitHubIssueTracker(token=cfg.github_token or "", repo=cfg.github_repo or "")
        if p == "gitlab":
            return GitLabIssueTracker(token=cfg.gitlab_token or "", project_id=cfg.gitlab_project_id or "", base_url=cfg.gitlab_url)
        if p == "jira":
            return JiraIssueTracker(base_url=cfg.jira_url or "", email=cfg.jira_email or "", api_token=cfg.jira_api_token or "", project_key=cfg.jira_project_key or "")
        raise ValueError("Unsupported or missing TRACKER_PROVIDER. Use one of: github, gitlab, jira")

    def create_issue_for_gap(self, gap: Dict[str, Any]) -> Dict[str, Any]:
        gid = str(gap.get("id") or gap.get("external_id"))
        title = gap.get("title") or f"Gap detected: {gid}"
        description = gap.get("description") or self._default_description(gap)
        labels = self._sanitize_list(gap.get("labels"))
        assignees = self._sanitize_list(gap.get("assignees"))

        # idempotency via local registry first
        existing = self.registry.get(gid)
        if existing:
            return {"created": False, "issue_id": existing.get("issue_id"), "issue_url": existing.get("issue_url")}

        # fallback dedupe via provider search using external id or fingerprint
        external_marker = self._make_external_marker(gid, gap)
        found = self.tracker.find_issue_by_external_id(external_marker)
        if found:
            self.registry.put(gid, found.get("issue_id"), found.get("issue_url"))
            return {"created": False, "issue_id": found.get("issue_id"), "issue_url": found.get("issue_url")}

        # Append external marker to description to enable search-based dedupe later
        full_body = f"{description}\n\nExternal-ID: {external_marker}"
        created = self.tracker.create_issue(title=title, body=full_body, labels=labels, assignees=assignees)
        self.registry.put(gid, created.get("issue_id"), created.get("issue_url"))
        return {"created": True, "issue_id": created.get("issue_id"), "issue_url": created.get("issue_url")}

    def _default_description(self, gap: Dict[str, Any]) -> str:
        parts: List[str] = []
        parts.append("An automated check detected a gap that needs attention.")
        severity = gap.get("severity")
        if severity:
            parts.append(f"Severity: {severity}")
        details = gap.get("details")
        if details:
            parts.append("Details:\n" + (details if isinstance(details, str) else str(details)))
        return "\n\n".join(parts)

    def _sanitize_list(self, val: Any) -> Optional[List[str]]:
        if not val:
            return None
        if isinstance(val, list):
            return [str(x) for x in val if x is not None]
        return [str(val)]

    def _make_external_marker(self, gid: str, gap: Dict[str, Any]) -> str:
        # Create a stable fingerprint of key gap inputs to make search robust
        fingerprint_src = f"{gid}|{gap.get('title','')}|{gap.get('severity','')}|{gap.get('category','')}"
        fp = hashlib.sha256(fingerprint_src.encode()).hexdigest()[:16]
        return f"gap:{gid}:{fp}"

