from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IssueTrackerError(Exception):
    pass


class IssueTracker(ABC):
    @abstractmethod
    def create_issue(self, title: str, body: str, labels: Optional[List[str]] = None, assignees: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Returns dict with keys: issue_id, issue_url
        """
        raise NotImplementedError

    @abstractmethod
    def find_issue_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Return issue details if an issue referencing external_id already exists, else None"""
        raise NotImplementedError

