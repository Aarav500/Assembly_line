from typing import Any, Dict, List
from ..config import config
from ..utils import k8s_name, now_suffix, merge_dicts, normalize_env, yaml_dump, boolish, image_pull_policy_for, inject_optional_pod_scheduling
from ..validators import validate_flux_payload


def _flux_kind_to_subcommand(kind: str) -> List[str]:
    low = kind.lower()
    if kind in {"GitRepository", "HelmRepository", "OCIRepository", "Bucket"}:
        return ["source", kind.replace("Repository", "").lower()]
    # Kustomization or HelmRelease
    return [low]


def _build_flux_command(payload: Dict[str, Any]) -> Dict[str, Any]:
    kind = payload["kind"]
    name = payload["name"]
    namespace = payload.get("namespace", "flux-system")

    sub = _flux_kind_to_subcommand(kind)

    cmd: List[str] = ["flux", "reconcile", *sub, name, "-n", namespace]

    with_source = boolish(payload.get("withSource"), False)
    if with_source and kind in {"Kustomization", "HelmRelease"}:
        cmd.append("--with-source")

    timeout = str(payload.get("timeout", "5m"))
    if timeout:
        cmd += ["--timeout", timeout]

    verbose = boolish(payload.get("verbose"), False)
    if verbose:
        cmd.append("--verbose")

    extra_args = payload.get("extraArgs") or []
    if isinstance(extra_args, list) and extra_args:
        cmd += [str(x) for x in extra_args]

    script = "set -euo pipefail ; " + " ".join(cmd)

    env = normalize_env(payload.get("env"))

    return {"script": script, "env": env}


def generate_flux_reconcile_job(payload: Dict[str, Any]) -> str:
    validate_flux_payload(payload)

    name = payload["name"]
    job_namespace = payload.get("jobNamespace") or config.DEFAULT_JOB_NAMESPACE

    base_job_name = payload.get("jobName") or k8s_name(f"flux-reconcile-{name}-{now_suffix()}")

    annotations = payload.get("annotations") or {}
    labels = merge_dicts(
        {
            "app.kubernetes.io/name": "flux-reconcile-job",
            "app.kubernetes.io/component": "reconcile",
            "kustomize.toolkit.fluxcd.io/name": name,
        },
        payload.get("labels") or {},
    )

    image = payload.get("image") or config.DEFAULT_FLUX_IMAGE
    image_pull_policy = payload.get("imagePullPolicy") or image_pull_policy_for(image)

    sa_name = payload.get("serviceAccountName") or config.DEFAULT_SERVICE_ACCOUNT
    backoff_limit = int(payload.get("backoffLimit", config.DEFAULT_BACKOFF_LIMIT))
    ttl_after = int(payload.get("ttlSecondsAfterFinished", config.DEFAULT_TTL_SECONDS_AFTER_FINISHED))

    cmd_info = _build_flux_command(payload)

    container_spec: Dict[str, Any] = {
        "name": "flux-reconcile",
        "image": image,
        "imagePullPolicy": image_pull_policy,
        "command": ["/bin/sh", "-c"],
        "args": [cmd_info["script"]],
        "env": cmd_info["env"],
        "securityContext": {
            "runAsNonRoot": True,
            "allowPrivilegeEscalation": False,
        },
    }

    if payload.get("resources"):
        container_spec["resources"] = payload["resources"]

    pod_spec: Dict[str, Any] = {
        "serviceAccountName": sa_name,
        "restartPolicy": payload.get("restartPolicy", "Never"),
        "containers": [container_spec],
    }

    if payload.get("imagePullSecrets"):
        pod_spec["imagePullSecrets"] = payload["imagePullSecrets"]

    inject_optional_pod_scheduling(pod_spec, payload)

    job_manifest: Dict[str, Any] = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": base_job_name,
            "namespace": job_namespace,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "backoffLimit": backoff_limit,
            "ttlSecondsAfterFinished": ttl_after,
            "template": {
                "metadata": {
                    "labels": labels,
                    "annotations": annotations,
                },
                "spec": pod_spec,
            },
        },
    }

    if payload.get("activeDeadlineSeconds"):
        job_manifest["spec"]["activeDeadlineSeconds"] = int(payload["activeDeadlineSeconds"])

    return yaml_dump(job_manifest)

