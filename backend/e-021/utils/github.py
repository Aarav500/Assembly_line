import json
import requests

class GitHubPR:
    def __init__(self, repository: str, token: str):
        self.repository = repository  # format: owner/repo
        self.token = token
        self.api = f"https://api.github.com/repos/{repository}"

    def create_pr(self, title: str, head: str, base: str, body: str = ""):
        url = f"{self.api}/pulls"
        payload = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "maintainer_can_modify": True,
            "draft": False,
        }
        resp = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=30)
        if resp.status_code >= 300:
            raise RuntimeError(f"GitHub PR creation failed: {resp.status_code} {resp.text}")
        return resp.json()

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }

