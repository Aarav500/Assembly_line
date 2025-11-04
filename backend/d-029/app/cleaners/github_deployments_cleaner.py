import logging
import requests

from .base import BaseCleaner, CleanupResult

logger = logging.getLogger(__name__)


class GitHubDeploymentsCleaner(BaseCleaner):
    def __init__(self, settings):
        super().__init__(settings, name="github-deployments")
        self.token = settings.github_token
        self.timeout = settings.http_timeout
        self.env_template = settings.environment_name_template
        self.delete_environment_enabled = settings.gh_environment_delete_enabled

    def _headers(self):
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}" if self.token else None,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _list_deployments(self, owner: str, repo: str, environment: str):
        page = 1
        per_page = 100
        while True:
            url = f"https://api.github.com/repos/{owner}/{repo}/deployments"
            params = {"per_page": per_page, "page": page, "environment": environment}
            resp = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed listing deployments: {resp.status_code} {resp.text}")
            data = resp.json()
            if not isinstance(data, list):
                break
            for d in data:
                yield d
            if len(data) < per_page:
                break
            page += 1

    def _set_deployment_inactive(self, owner: str, repo: str, deployment_id: int):
        url = f"https://api.github.com/repos/{owner}/{repo}/deployments/{deployment_id}/statuses"
        payload = {"state": "inactive", "auto_inactive": True}
        if self.dry_run:
            logger.info("[dry-run] Would set deployment %s inactive", deployment_id)
            return True
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        if resp.status_code not in (201, 200):
            logger.warning("Failed to set deployment %s inactive: %s %s", deployment_id, resp.status_code, resp.text)
            return False
        return True

    def _delete_deployment(self, owner: str, repo: str, deployment_id: int):
        url = f"https://api.github.com/repos/{owner}/{repo}/deployments/{deployment_id}"
        if self.dry_run:
            logger.info("[dry-run] Would delete deployment %s", deployment_id)
            return True
        resp = requests.delete(url, headers=self._headers(), timeout=self.timeout)
        if resp.status_code in (204, 200):
            return True
        # If cannot delete, we log and continue
        logger.warning("Failed deleting deployment %s: %s %s", deployment_id, resp.status_code, resp.text)
        return False

    def _delete_environment(self, owner: str, repo: str, environment_name: str):
        url = f"https://api.github.com/repos/{owner}/{repo}/environments/{environment_name}"
        if self.dry_run:
            logger.info("[dry-run] Would delete environment %s", environment_name)
            return True
        resp = requests.delete(url, headers=self._headers(), timeout=self.timeout)
        if resp.status_code in (204, 200, 404):
            return True
        logger.warning("Failed deleting environment %s: %s %s", environment_name, resp.status_code, resp.text)
        return False

    def cleanup(self, ctx: dict) -> CleanupResult:
        if not self.token:
            return {"name": self.name, "ok": True, "details": {"skipped": "No GITHUB_TOKEN provided"}}

        owner = ctx.get("repo_owner")
        repo = ctx.get("repo_name")
        env_name = self.settings.format_template(self.env_template, ctx)

        try:
            matched = 0
            deleted = 0
            inactivated = 0
            for dep in self._list_deployments(owner, repo, env_name):
                matched += 1
                dep_id = dep.get("id")
                if self._set_deployment_inactive(owner, repo, dep_id):
                    inactivated += 1
                if self._delete_deployment(owner, repo, dep_id):
                    deleted += 1

            env_deleted = False
            if self.delete_environment_enabled:
                env_deleted = self._delete_environment(owner, repo, env_name)

            return {
                "name": self.name,
                "ok": True,
                "details": {
                    "repo": f"{owner}/{repo}",
                    "environment": env_name,
                    "deployments_matched": matched,
                    "deployments_inactivated": inactivated,
                    "deployments_deleted": deleted,
                    "environment_deleted": env_deleted,
                    "dry_run": self.dry_run,
                },
            }
        except Exception as e:
            return {"name": self.name, "ok": False, "error": str(e)}

