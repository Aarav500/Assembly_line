import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        # Web server
        self.PORT = os.getenv("PORT", "8000")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # Webhook security
        self.GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

        # GitHub API
        self.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
        self.GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")
        self.GITHUB_GRAPHQL_URL = os.getenv("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")
        self.GITHUB_APP_USER_AGENT = os.getenv("GITHUB_APP_USER_AGENT", "ci-repro-bot/1.0")

        # Behavior
        self.ENABLE_ISSUE_CREATION = os.getenv("ENABLE_ISSUE_CREATION", "true").lower() == "true"
        self.ENABLE_PR_CREATION = os.getenv("ENABLE_PR_CREATION", "true").lower() == "true"
        self.PR_DRAFT = os.getenv("PR_DRAFT", "true").lower() == "true"
        self.PR_BRANCH_PREFIX = os.getenv("PR_BRANCH_PREFIX", "ci-repro/run-")
        self.DEFAULT_LABELS = [s.strip() for s in os.getenv("DEFAULT_LABELS", "ci,auto-created,bot").split(",") if s.strip()]
        self.DEFAULT_ASSIGNEES = [s.strip() for s in os.getenv("DEFAULT_ASSIGNEES", "").split(",") if s.strip()]
        self.REPO_ALLOWLIST = [s.strip() for s in os.getenv("REPO_ALLOWLIST", "").split(",") if s.strip()]
        self.ALLOW_PRIVATE_REPOS = os.getenv("ALLOW_PRIVATE_REPOS", "true").lower() == "true"
        self.CONTENT_COMMIT_AUTHOR_NAME = os.getenv("CONTENT_COMMIT_AUTHOR_NAME", "ci-repro-bot")
        self.CONTENT_COMMIT_AUTHOR_EMAIL = os.getenv("CONTENT_COMMIT_AUTHOR_EMAIL", "ci-repro-bot@example.com")

        # Parsing
        self.MAX_LOG_BYTES = int(os.getenv("MAX_LOG_BYTES", str(4 * 1024 * 1024)))  # 4MB cap per job log

    def repo_allowed(self, full_name: str, private: bool) -> bool:
        if not self.ALLOW_PRIVATE_REPOS and private:
            return False
        if not self.REPO_ALLOWLIST:
            return True
        return full_name in self.REPO_ALLOWLIST

