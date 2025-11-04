from typing import Any, Dict, List, Tuple
from .utils import k8s_name


class InputError(ValueError):
    pass


def _require(data: Dict[str, Any], key: str, msg: str = None) -> Any:
    if key not in data or data[key] in (None, ""):
        raise InputError(msg or f"Missing required field: {key}")
    return data[key]


def validate_argocd_payload(payload: Dict[str, Any]) -> None:
    _require(payload, "appName", "appName is required")
    # server can be defaulted by config, but if provided, should be non-empty
    # auth: either token or username/password
    auth = payload.get("auth", {}) or {}
    if not (auth.get("token") or (auth.get("username") and auth.get("password"))):
        raise InputError("auth.token or auth.username/password required")
    # Optional: jobName must be DNS-1123 compliant if provided
    if payload.get("jobName"):
        payload["jobName"] = k8s_name(str(payload["jobName"]))


def validate_flux_payload(payload: Dict[str, Any]) -> None:
    kind = _require(payload, "kind", "kind is required (e.g. Kustomization, HelmRelease, GitRepository, HelmRepository)")
    name = _require(payload, "name", "name is required")
    allowed = {"Kustomization", "HelmRelease", "GitRepository", "HelmRepository", "OCIRepository", "Bucket"}
    if kind not in allowed:
        raise InputError(f"Unsupported kind: {kind}. Allowed: {', '.join(sorted(allowed))}")
    # sanitize provided jobName if any
    if payload.get("jobName"):
        payload["jobName"] = k8s_name(str(payload["jobName"]))


def validate_k8s_job_manifest(manifest: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(manifest, dict):
        return False, ["Manifest must be a dictionary"]

    api_version = manifest.get("apiVersion")
    kind = manifest.get("kind")
    if api_version != "batch/v1":
        errors.append("apiVersion must be 'batch/v1'")
    if kind != "Job":
        errors.append("kind must be 'Job'")

    metadata = manifest.get("metadata") or {}
    name = metadata.get("name")
    if not name:
        errors.append("metadata.name is required")

    spec = manifest.get("spec") or {}
    template = spec.get("template") or {}
    pod_spec = (template.get("spec") or {})
    containers = pod_spec.get("containers") or []

    if not containers or not isinstance(containers, list):
        errors.append("spec.template.spec.containers must be a non-empty list")
    else:
        for i, c in enumerate(containers):
            if not c.get("name"):
                errors.append(f"container[{i}].name is required")
            if not c.get("image"):
                errors.append(f"container[{i}].image is required")

    rp = pod_spec.get("restartPolicy")
    if rp not in {"Never", "OnFailure"}:
        errors.append("spec.template.spec.restartPolicy must be 'Never' or 'OnFailure'")

    return (len(errors) == 0, errors)

