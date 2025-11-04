import requests
from typing import Dict, List, Optional

class GitHubClient:
    def __init__(self, token: str, api_url: str, scope: str, owner: str = "", repo: str = "", org: str = ""):
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.scope = scope
        self.owner = owner
        self.repo = repo
        self.org = org
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "runner-fleet-manager/1.0"
        })

    def _url(self, path: str) -> str:
        return f"{self.api_url}{path}"

    def _scope_prefix(self) -> str:
        if self.scope == "org":
            return f"/orgs/{self.org}"
        else:
            return f"/repos/{self.owner}/{self.repo}"

    def get_registration_token(self) -> str:
        path = f"{self._scope_prefix()}/actions/runners/registration-token"
        r = self.session.post(self._url(path))
        r.raise_for_status()
        data = r.json()
        return data["token"]

    def list_runners(self) -> List[Dict]:
        path = f"{self._scope_prefix()}/actions/runners"
        r = self.session.get(self._url(path), params={"per_page": 100})
        r.raise_for_status()
        data = r.json()
        return data.get("runners", [])

    def count_queued_workflow_runs(self) -> int:
        # Only available at repo scope; for org we sum across repos would be expensive.
        if self.scope == "org":
            return 0
        path = f"/repos/{self.owner}/{self.repo}/actions/runs"
        r = self.session.get(self._url(path), params={"status": "queued", "per_page": 1})
        r.raise_for_status()
        data = r.json()
        return int(data.get("total_count", 0))

    def remove_runner(self, runner_id: int) -> bool:
        path = f"{self._scope_prefix()}/actions/runners/{runner_id}"
        r = self.session.delete(self._url(path))
        return r.status_code in (200, 204)

