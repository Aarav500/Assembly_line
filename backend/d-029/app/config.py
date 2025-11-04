import os
from dataclasses import dataclass


def _get_bool(env_name: str, default: bool = False) -> bool:
    val = os.getenv(env_name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _get_list(env_name: str, default: list[str] | None = None, sep: str = ",") -> list[str]:
    raw = os.getenv(env_name)
    if raw is None or raw.strip() == "":
        return default or []
    return [x.strip() for x in raw.split(sep) if x.strip()]


@dataclass
class Settings:
    # General
    debug: bool
    dry_run: bool

    # Webhook
    github_webhook_secret: str | None
    insecure_disable_signature_verification: bool

    # GitHub API
    github_token: str | None
    http_timeout: int

    # S3 cleanup
    s3_enabled: bool
    s3_bucket: str | None
    s3_prefix_template: str

    # Kubernetes cleanup
    k8s_enabled: bool
    k8s_namespace_template: str
    k8s_context: str | None

    # GitHub artifacts cleanup
    gh_artifacts_enabled: bool
    artifact_name_patterns: list[str]

    # GitHub deployments/environment cleanup
    gh_deployments_enabled: bool
    gh_environment_delete_enabled: bool
    environment_name_template: str

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            debug=_get_bool("DEBUG", False),
            dry_run=_get_bool("DRY_RUN", True),
            github_webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET"),
            insecure_disable_signature_verification=_get_bool(
                "INSECURE_DISABLE_SIGNATURE_VERIFICATION", False
            ),
            github_token=os.getenv("GITHUB_TOKEN"),
            http_timeout=int(os.getenv("HTTP_TIMEOUT", "15")),
            s3_enabled=_get_bool("ENABLE_S3_CLEANUP", False),
            s3_bucket=os.getenv("S3_BUCKET"),
            s3_prefix_template=os.getenv("S3_PREFIX_TEMPLATE", "previews/pr-{pr}/"),
            k8s_enabled=_get_bool("ENABLE_K8S_CLEANUP", False),
            k8s_namespace_template=os.getenv("K8S_NAMESPACE_TEMPLATE", "preview-pr-{pr}"),
            k8s_context=os.getenv("K8S_CONTEXT"),
            gh_artifacts_enabled=_get_bool("ENABLE_GH_ARTIFACTS_CLEANUP", False),
            artifact_name_patterns=_get_list(
                "ARTIFACT_NAME_PATTERNS", ["pr-{pr}", "preview-pr-{pr}"]
            ),
            gh_deployments_enabled=_get_bool("ENABLE_GH_DEPLOYMENTS_CLEANUP", False),
            gh_environment_delete_enabled=_get_bool("ENABLE_GH_ENVIRONMENT_DELETE", False),
            environment_name_template=os.getenv("ENVIRONMENT_NAME_TEMPLATE", "pr-{pr}"),
        )

    def format_template(self, template: str, ctx: dict) -> str:
        # Only allow formatting placeholders we expect
        safe_ctx = {
            "pr": ctx.get("pr_number"),
            "owner": ctx.get("repo_owner"),
            "repo": ctx.get("repo_name"),
            "branch": ctx.get("branch"),
        }
        try:
            return template.format(**safe_ctx)
        except KeyError:
            # If template contains unsupported placeholders, just return as-is
            return template

