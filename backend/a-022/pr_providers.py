import requests
from typing import Dict


class GitHubProvider:
    def __init__(self, token: str, host: str = "github.com", api_base: str | None = None):
        self.host = host
        if api_base:
            self.api_base = api_base
        else:
            if host.endswith("github.com"):
                self.api_base = "https://api.github.com"
            else:
                self.api_base = f"https://{host}/api/v3"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "git-sync-controls-ui/1.0",
        })

    def create_pr(self, owner: str, repo: str, title: str, body: str, head: str, base: str, draft: bool = False) -> Dict:
        url = f"{self.api_base}/repos/{owner}/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
        }
        resp = self.session.post(url, json=payload, timeout=30)
        if resp.status_code >= 300:
            try:
                data = resp.json()
            except Exception:
                data = {"message": resp.text}
            raise RuntimeError(f"GitHub PR creation failed: {data}")
        data = resp.json()
        return {
            "number": data.get("number"),
            "url": data.get("html_url"),
            "state": data.get("state"),
            "title": data.get("title"),
            "head": data.get("head", {}).get("ref"),
            "base": data.get("base", {}).get("ref"),
        }


def get_pr_provider(host: str, token: str):
    # Currently only GitHub
    if "github" in host:
        return GitHubProvider(token=token, host=host)
    raise NotImplementedError(f"PR provider for host '{host}' is not implemented")

