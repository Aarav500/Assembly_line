import os


def get_env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in {"1", "true", "yes", "on"}


class Config:
    DEBUG = get_env_bool("DEBUG", False)

    DEFAULT_JOB_NAMESPACE = os.getenv("DEFAULT_JOB_NAMESPACE", "default")
    DEFAULT_SERVICE_ACCOUNT = os.getenv("DEFAULT_SERVICE_ACCOUNT", "default")
    DEFAULT_BACKOFF_LIMIT = int(os.getenv("DEFAULT_BACKOFF_LIMIT", "0"))
    DEFAULT_TTL_SECONDS_AFTER_FINISHED = int(os.getenv("DEFAULT_TTL_SECONDS_AFTER_FINISHED", "600"))

    DEFAULT_ARGOCD_IMAGE = os.getenv("DEFAULT_ARGOCD_IMAGE", "quay.io/argoproj/argocd:latest")
    DEFAULT_FLUX_IMAGE = os.getenv("DEFAULT_FLUX_IMAGE", "ghcr.io/fluxcd/flux-cli:latest")
    DEFAULT_IMAGE_PULL_POLICY = os.getenv("DEFAULT_IMAGE_PULL_POLICY", "IfNotPresent")

    DEFAULT_ARGOCD_SERVER = os.getenv("DEFAULT_ARGOCD_SERVER", "argocd-server.argocd.svc.cluster.local:443")

    # Security context defaults
    RUN_AS_NON_ROOT = get_env_bool("RUN_AS_NON_ROOT", True)
    ALLOW_PRIVILEGE_ESCALATION = get_env_bool("ALLOW_PRIVILEGE_ESCALATION", False)

    # Optional Job pod settings
    DEFAULT_NODE_SELECTOR = os.getenv("DEFAULT_NODE_SELECTOR", "")  # e.g. "disktype=ssd,zone=us"
    DEFAULT_TOLERATIONS = os.getenv("DEFAULT_TOLERATIONS", "")  # JSON string if provided
    DEFAULT_AFFINITY = os.getenv("DEFAULT_AFFINITY", "")  # JSON string if provided


config = Config()

