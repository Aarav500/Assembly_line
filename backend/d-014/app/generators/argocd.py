from typing import Any, Dict, List
from ..config import config
from ..utils import k8s_name, now_suffix, merge_dicts, normalize_env, yaml_dump, boolish, image_pull_policy_for, inject_optional_pod_scheduling
from ..validators import validate_argocd_payload


def _build_argocd_commands(payload: Dict[str, Any]) -> Dict[str, Any]:
    app_name = payload["appName"]
    server = payload.get("argocdServer") or config.DEFAULT_ARGOCD_SERVER

    grpc_web = boolish(payload.get("grpcWeb"), True)
    insecure = boolish(payload.get("insecure"), False)
    wait = boolish(payload.get("wait"), True)
    wait_timeout = int(payload.get("waitTimeoutSeconds", 600))

    flags: List[str] = []
    if grpc_web:
        flags.append("--grpc-web")
    if insecure:
        flags.append("--insecure")

    revision = payload.get("revision")
    prune = boolish(payload.get("prune"), False)
    dry_run = boolish(payload.get("dryRun"), False)

    extra_args = payload.get("extraArgs") or []
    if not isinstance(extra_args, list):
        extra_args = []

    auth = payload.get("auth") or {}
    token = auth.get("token")
    username = auth.get("username")
    password = auth.get("password")

    env = []
    parts: List[str] = [
        "set -euo pipefail"
    ]

    if token:
        env.append({"name": "ARGOCD_AUTH_TOKEN", "value": str(token)})
        sync_cmd = [
            "argocd", "app", "sync", app_name,
            "--server", server,
            *flags,
        ]
        if revision:
            sync_cmd += ["--revision", str(revision)]
        if prune:
            sync_cmd.append("--prune")
        if dry_run:
            sync_cmd.append("--dry-run")
        if extra_args:
            sync_cmd += [str(x) for x in extra_args]
        parts.append(" ".join(sync_cmd))

        if wait:
            wait_cmd = [
                "argocd", "app", "wait", app_name,
                "--sync", "--health",
                "--timeout", str(wait_timeout),
                "--server", server,
                *flags,
            ]
            # token is consumed automatically by CLI if provided to command via env only for login;
            # here we pass token explicitly for each command to ensure auth with server.
            wait_cmd += ["--auth-token", "$ARGOCD_AUTH_TOKEN"]
            parts.append(" ".join(wait_cmd))

        # For sync, add token as well to avoid relying on previous state
        parts[1] = parts[1] + f" --auth-token $ARGOCD_AUTH_TOKEN"

    elif username and password:
        env.append({"name": "ARGOCD_USERNAME", "value": str(username)})
        env.append({"name": "ARGOCD_PASSWORD", "value": str(password)})
        login_cmd = [
            "argocd", "login", server,
            *flags,
            "--username", "$ARGOCD_USERNAME",
            "--password", "$ARGOCD_PASSWORD",
        ]
        parts.append(" ".join(login_cmd))

        sync_cmd = [
            "argocd", "app", "sync", app_name,
            *flags,
            "--server", server,
        ]
        if revision:
            sync_cmd += ["--revision", str(revision)]
        if prune:
            sync_cmd.append("--prune")
        if dry_run:
            sync_cmd.append("--dry-run")
        if extra_args:
            sync_cmd += [str(x) for x in extra_args]
        parts.append(" ".join(sync_cmd))

        if wait:
            wait_cmd = [
                "argocd", "app", "wait", app_name,
                "--sync", "--health",
                "--timeout", str(wait_timeout),
            ]
            parts.append(" ".join(wait_cmd))
    else:
        # This should be prevented by validation, but just in case
        raise ValueError("No valid ArgoCD auth provided")

    # User-provided env
    user_env = normalize_env(payload.get("env"))
    env = env + user_env

    cmd_script = " ; ".join(parts)
    return {"script": cmd_script, "env": env}


def generate_argocd_sync_job(payload: Dict[str, Any]) -> str:
    validate_argocd_payload(payload)

    app_name = payload["appName"]
    job_namespace = payload.get("jobNamespace") or payload.get("namespace") or config.DEFAULT_JOB_NAMESPACE

    base_job_name = payload.get("jobName") or k8s_name(f"argocd-sync-{app_name}-{now_suffix()}")

    annotations = payload.get("annotations") or {}
    labels = merge_dicts(
        {
            "app.kubernetes.io/name": "argocd-sync-job",
            "app.kubernetes.io/component": "sync",
            "argocd.argoproj.io/app-name": app_name,
        },
        payload.get("labels") or {},
    )

    image = payload.get("image") or config.DEFAULT_ARGOCD_IMAGE
    image_pull_policy = payload.get("imagePullPolicy") or image_pull_policy_for(image)

    sa_name = payload.get("serviceAccountName") or config.DEFAULT_SERVICE_ACCOUNT
    backoff_limit = int(payload.get("backoffLimit", config.DEFAULT_BACKOFF_LIMIT))
    ttl_after = int(payload.get("ttlSecondsAfterFinished", config.DEFAULT_TTL_SECONDS_AFTER_FINISHED))

    cmd_info = _build_argocd_commands(payload)

    container_spec: Dict[str, Any] = {
        "name": "argocd-sync",
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

    # Support setting resources if provided
    if payload.get("resources"):
        container_spec["resources"] = payload["resources"]

    pod_spec: Dict[str, Any] = {
        "serviceAccountName": sa_name,
        "restartPolicy": payload.get("restartPolicy", "Never"),
        "containers": [container_spec],
    }

    # Optional fields
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

    # Optional activeDeadlineSeconds
    if payload.get("activeDeadlineSeconds"):
        job_manifest["spec"]["activeDeadlineSeconds"] = int(payload["activeDeadlineSeconds"])

    return yaml_dump(job_manifest)

