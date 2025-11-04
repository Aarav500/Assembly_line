import logging
from typing import Any

from ..config import Settings
from ..cleaners.base import CleanupResult
from ..cleaners.s3_cleaner import S3Cleaner
from ..cleaners.kubernetes_cleaner import KubernetesNamespaceCleaner
from ..cleaners.github_artifacts_cleaner import GitHubArtifactsCleaner
from ..cleaners.github_deployments_cleaner import GitHubDeploymentsCleaner

logger = logging.getLogger(__name__)


def build_cleaners(settings: Settings):
    cleaners = []
    if settings.s3_enabled:
        cleaners.append(S3Cleaner(settings))
    if settings.k8s_enabled:
        cleaners.append(KubernetesNamespaceCleaner(settings))
    if settings.gh_artifacts_enabled:
        cleaners.append(GitHubArtifactsCleaner(settings))
    if settings.gh_deployments_enabled:
        cleaners.append(GitHubDeploymentsCleaner(settings))
    return cleaners


def cleanup_for_pr(ctx: dict[str, Any], settings: Settings) -> list[CleanupResult]:
    cleaners = build_cleaners(settings)
    results: list[CleanupResult] = []
    if not cleaners:
        logger.info("No cleaners enabled. Nothing to do.")
        return []

    logger.info(
        "Starting cleanup for %s PR#%s using %d cleaner(s) (dry-run=%s)",
        ctx.get("repo_full_name"), ctx.get("pr_number"), len(cleaners), settings.dry_run
    )

    for cleaner in cleaners:
        try:
            res = cleaner.cleanup(ctx)
            results.append(res)
            status = "ok" if res.get("ok") else "failed"
            logger.info("%s: %s", res.get("name"), status)
        except Exception as e:
            logger.exception("Cleaner %s failed: %s", cleaner.name, e)
            results.append({
                "name": cleaner.name,
                "ok": False,
                "error": str(e),
            })
    return results

