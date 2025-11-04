import os
from dataclasses import dataclass


@dataclass
class Config:
    tracker_provider: str
    auto_create_issues: bool

    # GitHub
    github_token: str | None
    github_repo: str | None  # format: owner/repo

    # GitLab
    gitlab_token: str | None
    gitlab_project_id: str | None
    gitlab_url: str

    # Jira
    jira_url: str | None
    jira_email: str | None
    jira_api_token: str | None
    jira_project_key: str | None

    # Registry
    issue_registry_path: str

    @staticmethod
    def from_env() -> "Config":
        provider = (os.getenv("TRACKER_PROVIDER", "").strip().lower())
        return Config(
            tracker_provider=provider,
            auto_create_issues=os.getenv("AUTO_CREATE_ISSUES", "true").lower() in ("1", "true", "yes"),
            github_token=os.getenv("GITHUB_TOKEN"),
            github_repo=os.getenv("GITHUB_REPO"),
            gitlab_token=os.getenv("GITLAB_TOKEN"),
            gitlab_project_id=os.getenv("GITLAB_PROJECT_ID"),
            gitlab_url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            jira_url=os.getenv("JIRA_URL"),
            jira_email=os.getenv("JIRA_EMAIL"),
            jira_api_token=os.getenv("JIRA_API_TOKEN"),
            jira_project_key=os.getenv("JIRA_PROJECT_KEY"),
            issue_registry_path=os.getenv("ISSUE_REGISTRY_PATH", ".data/issue_registry.json"),
        )

