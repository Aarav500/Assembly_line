import base64
import json
import requests

GITHUB_API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str):
        if not token:
            raise ValueError("GitHub token is required")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "mv-one-line-fixer/1.0"
        })

    def _raise_for_status(self, resp):
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            detail = None
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"GitHub API error {resp.status_code}: {detail}") from e

    def get_ref_sha(self, owner: str, repo: str, branch: str) -> str:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
        r = self.session.get(url)
        self._raise_for_status(r)
        data = r.json()
        return data["object"]["sha"]

    def create_branch(self, owner: str, repo: str, new_branch: str, from_branch: str):
        # If branch exists, treat as success
        ref_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{new_branch}"
        r = self.session.get(ref_url)
        if r.status_code == 200:
            return

        base_sha = self.get_ref_sha(owner, repo, from_branch)
        url = f"{GITHUB_API}/repos/{owner}/{repo}/git/refs"
        payload = {"ref": f"refs/heads/{new_branch}", "sha": base_sha}
        r = self.session.post(url, json=payload)
        if r.status_code == 422:
            # Unprocessable Entity - branch might already exist due to race; ignore
            return
        self._raise_for_status(r)

    def get_file(self, owner: str, repo: str, path: str, ref: str):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        r = self.session.get(url, params={"ref": ref})
        self._raise_for_status(r)
        data = r.json()
        if isinstance(data, list):
            raise RuntimeError("Path refers to a directory, not a file")
        content_b64 = data.get("content", "")
        if data.get("encoding") == "base64":
            content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        else:
            content = content_b64
        return content, data.get("sha")

    def update_file(self, owner: str, repo: str, path: str, new_content: str, message: str, branch: str, sha: str = None):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        content_b64 = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
        payload = {
            "message": message,
            "content": content_b64,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        r = self.session.put(url, json=payload)
        self._raise_for_status(r)
        return r.json()

    def create_pr(self, owner: str, repo: str, title: str, body: str, head_branch: str, base_branch: str):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "maintainer_can_modify": True,
            "draft": False
        }
        r = self.session.post(url, json=payload)
        self._raise_for_status(r)
        data = r.json()
        return {
            "number": data.get("number"),
            "url": data.get("html_url"),
            "state": data.get("state"),
            "title": data.get("title"),
            "head": data.get("head", {}).get("ref"),
            "base": data.get("base", {}).get("ref"),
        }

