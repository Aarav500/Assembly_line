import os
import requests
from typing import List, Tuple, Optional


class GitHubClient:
    def __init__(self, token: str, repo: str):
        self.token = token or ""
        self.repo = repo or ""
        self._session = requests.Session()
        if self.token:
            self._session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "auto-detect-regressions-bot"
            })

    def enabled(self) -> bool:
        return bool(self.token and self.repo and "/" in self.repo)

    def _owner_repo(self):
        owner, repo = self.repo.split("/", 1)
        return owner, repo

    def get_prs_for_commit(self, sha: str) -> List[Tuple[int, Optional[str]]]:
        if not self.enabled() or not sha:
            return []
        owner, repo = self._owner_repo()
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/pulls"
        # This endpoint returns PRs associated with the commit
        try:
            r = self._session.get(url)
            if r.status_code != 200:
                return []
            data = r.json()
            prs = []
            for pr in data:
                num = pr.get("number")
                user = (pr.get("user") or {}).get("login")
                if num is not None:
                    prs.append((int(num), user))
            return prs
        except Exception:
            return []

    def comment_on_pr(self, pr_number: int, body: str) -> Optional[str]:
        if not self.enabled():
            return None
        owner, repo = self._owner_repo()
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        r = self._session.post(url, json={"body": body})
        if r.status_code in (200, 201):
            return r.json().get("html_url")
        return None

    def create_issue(self, title: str, body: str, labels: Optional[list] = None) -> Optional[str]:
        if not self.enabled():
            return None
        owner, repo = self._owner_repo()
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        r = self._session.post(url, json=payload)
        if r.status_code in (200, 201):
            return r.json().get("html_url")
        return None

