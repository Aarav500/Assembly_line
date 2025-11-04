import os

class Config:
    def __init__(self):
        # GitHub configuration
        self.GH_TOKEN = os.getenv("GH_TOKEN", "")
        self.GH_API_URL = os.getenv("GH_API_URL", "https://api.github.com")
        self.REPO_OWNER = os.getenv("REPO_OWNER", "")
        self.REPO_NAME = os.getenv("REPO_NAME", "")
        self.ORG_NAME = os.getenv("ORG_NAME", "")  # optional for org-level runners
        self.SCOPE = os.getenv("SCOPE", "repo").lower()  # "repo" or "org"

        # Scaling parameters
        self.SCALE_INTERVAL_SECONDS = _int(os.getenv("SCALE_INTERVAL_SECONDS", "30"), 30)
        self.MIN_CAPACITY = _int(os.getenv("MIN_CAPACITY", "0"), 0)
        self.MAX_CAPACITY = _int(os.getenv("MAX_CAPACITY", "10"), 10)
        self.DESIRED_CAPACITY = _int(os.getenv("DESIRED_CAPACITY", str(self.MIN_CAPACITY)), self.MIN_CAPACITY)
        self.SCALE_DOWN_IDLE_MINUTES = _int(os.getenv("SCALE_DOWN_IDLE_MINUTES", "10"), 10)
        self.SCALE_POLICY = os.getenv("SCALE_POLICY", "busy_plus_queued")  # simple policy name

        # Runner settings
        self.RUNNER_LABELS = os.getenv("RUNNER_LABELS", "self-hosted,linux,x64,fleet")
        self.RUNNER_NAME_PREFIX = os.getenv("RUNNER_NAME_PREFIX", "gh-runner")

        # Docker provisioning
        self.DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "myoung34/github-runner:latest")
        self.DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "")
        self.MOUNT_DOCKER_SOCK = os.getenv("MOUNT_DOCKER_SOCK", "true").lower() in ("1", "true", "yes")
        self.RUNNER_WORKDIR = os.getenv("RUNNER_WORKDIR", "/_work")

        # Persistence
        self.DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.abspath(os.getenv("DATABASE_FILE", "fleet.sqlite3")))

        # Security
        self.ALLOW_MANUAL_PROVISION = os.getenv("ALLOW_MANUAL_PROVISION", "true").lower() in ("1", "true", "yes")

        # Server
        self.ENV = os.getenv("FLASK_ENV", "production")

    def __getitem__(self, key):
        return getattr(self, key)


def _int(val, default):
    try:
        return int(val)
    except Exception:
        return default

