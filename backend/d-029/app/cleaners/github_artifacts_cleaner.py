import logging
import requests

from .base import BaseCleaner, CleanupResult

logger = logging.getLogger(__name__)


class GitHubArtifactsCleaner(BaseCleaner):
    def __init__(self, settings):
        super().__init__(settings, name="github-artifacts")
        self.token = settings.github_token
        self.timeout = settings.http_timeout
        self.patterns = settings.artifact_name_patterns

    def _headers(self):
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}" if self.token else None,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _list_artifacts(self, owner: str, repo: str):
        page = 1
        per_page = 100
        while True:
            url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts"
            resp = requests.get(url, headers=self._headers(), params={"per_page": per_page, "page": page}, timeout=self.timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed listing artifacts: {resp.status_code} {resp.text}")
            data = resp.json()
            artifacts = data.get("artifacts", [])
            for art in artifacts:
                yield art
            if len(artifacts) < per_page:
                break
            page += 1

    def _delete_artifact(self, owner: str, repo: str, artifact_id: int) -> bool:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts/{artifact_id}"
        if self.dry_run:
            logger.info("[dry-run] Would delete GitHub artifact id=%s", artifact_id)
            return True
        resp = requests.delete(url, headers=self._headers(), timeout=self.timeout)
        if resp.status_code in (204, 200):
            return True
        # 404 means already deleted or not found
        if resp.status_code == 404:
            return True
        logger.warning("Failed deleting artifact %s: %s %s", artifact_id, resp.status_code, resp.text)
        return False

    def cleanup(self, ctx: dict) -> CleanupResult:
        if not self.token:
            return {"name": self.name, "ok": True, "details": {"skipped": "No GITHUB_TOKEN provided"}}
        owner = ctx.get("repo_owner")
        repo = ctx.get("repo_name")
        pr = ctx.get("pr_number")

        # Build expected patterns for this PR
        targets = [self.settings.format_template(p, ctx) for p in self.patterns]

        try:
            matched = 0
            deleted = 0
            for art in self._list_artifacts(owner, repo):
                name = art.get("name", "")
                if any(t in name or name.startswith(t) for t in targets):
                    matched += 1
                    ok = self._delete_artifact(owner, repo, art.get("id"))
                    if ok:
                        deleted += 1
            return {
                "name": self.name,
                "ok": True,
                "details": {
                    "repo": f"{owner}/{repo}",
                    "pr": pr,
                    "patterns": targets,
                    "matched": matched,
                    "deleted": deleted,
                    "dry_run": self.dry_run,
                },
            }
        except Exception as e:
            return {"name": self.name, "ok": False, "error": str(e)}

