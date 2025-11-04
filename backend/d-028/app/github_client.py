import base64
import io
import logging
from typing import Dict, List, Optional, Tuple
import requests
from flask import current_app


class GitHubClient:
    def __init__(self, token: Optional[str] = None, api_url: Optional[str] = None):
        self.token = token or current_app.config.get("GITHUB_TOKEN")
        self.api_url = api_url or current_app.config.get("GITHUB_API_URL", "https://api.github.com")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}" if self.token else "",
            "User-Agent": current_app.config.get("GITHUB_APP_USER_AGENT", "ci-repro-bot/1.0"),
        })

    def _url(self, path: str) -> str:
        return f"{self.api_url}{path}"

    def create_issue(self, owner: str, repo: str, title: str, body: str, labels: List[str], assignees: List[str]) -> Dict:
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees
        r = self.session.post(self._url(f"/repos/{owner}/{repo}/issues"), json=payload)
        if r.status_code >= 300:
            logging.error("Create issue failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()

    def get_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        r = self.session.get(self._url(f"/repos/{owner}/{repo}/git/ref/heads/{branch}"))
        if r.status_code >= 300:
            logging.error("Get branch sha failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()["object"]["sha"]

    def create_branch(self, owner: str, repo: str, branch_name: str, sha: str) -> Dict:
        r = self.session.post(self._url(f"/repos/{owner}/{repo}/git/refs"), json={
            "ref": f"refs/heads/{branch_name}",
            "sha": sha
        })
        if r.status_code == 422 and "Reference already exists" in r.text:
            # Already exists; treat as success
            return {"ref": f"refs/heads/{branch_name}", "object": {"sha": sha}}
        if r.status_code >= 300:
            logging.error("Create branch failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()

    def get_file_sha(self, owner: str, repo: str, path: str, ref: str) -> Optional[str]:
        r = self.session.get(self._url(f"/repos/{owner}/{repo}/contents/{path}"), params={"ref": ref})
        if r.status_code == 404:
            return None
        if r.status_code >= 300:
            logging.error("Get file sha failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json().get("sha")

    def create_or_update_file(self, owner: str, repo: str, path: str, content_bytes: bytes, message: str, branch: str, author: Optional[Dict] = None) -> Dict:
        b64 = base64.b64encode(content_bytes).decode("ascii")
        existing_sha = self.get_file_sha(owner, repo, path, branch)
        payload = {
            "message": message,
            "content": b64,
            "branch": branch,
        }
        if author:
            payload["committer"] = author
            payload["author"] = author
        if existing_sha:
            payload["sha"] = existing_sha
        r = self.session.put(self._url(f"/repos/{owner}/{repo}/contents/{path}"), json=payload)
        if r.status_code >= 300:
            logging.error("Create or update file failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()

    def create_pr(self, owner: str, repo: str, head_branch: str, base_branch: str, title: str, body: str, draft: bool = False) -> Dict:
        payload = {
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body,
            "draft": draft,
        }
        r = self.session.post(self._url(f"/repos/{owner}/{repo}/pulls"), json=payload)
        if r.status_code == 422 and "A pull request already exists" in r.text:
            return {"message": "PR already exists"}
        if r.status_code >= 300:
            logging.error("Create PR failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int) -> Dict:
        r = self.session.get(self._url(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"), params={"per_page": 100})
        if r.status_code >= 300:
            logging.error("Get workflow jobs failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()

    def get_job_logs_text(self, owner: str, repo: str, job_id: int, max_bytes: int) -> str:
        # The API returns a gzip stream; requests will not automatically unzip unless headers included
        r = self.session.get(self._url(f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"), stream=True)
        if r.status_code >= 300:
            logging.error("Get job logs failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        # The response is a gzip file; using content decode
        # requests auto-decompresses when Content-Encoding: gzip
        buf = io.BytesIO()
        read_bytes = 0
        for chunk in r.iter_content(chunk_size=65536):
            if not chunk:
                break
            if read_bytes + len(chunk) > max_bytes:
                # Truncate
                buf.write(chunk[: max_bytes - read_bytes])
                read_bytes = max_bytes
                break
            buf.write(chunk)
            read_bytes += len(chunk)
        data = buf.getvalue()
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin1", errors="replace")
        return text

