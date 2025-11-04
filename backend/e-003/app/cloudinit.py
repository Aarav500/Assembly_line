import yaml
from typing import Any, Dict, List


def _ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [v for v in value.split("\n") if v.strip()]
    return [value]


def build_cloud_config(payload: Dict[str, Any]) -> str:
    cfg: Dict[str, Any] = {}

    hostname = payload.get("hostname")
    if hostname:
        cfg["hostname"] = hostname

    timezone = payload.get("timezone")
    if timezone:
        cfg["timezone"] = timezone

    # Users
    users: List[Dict[str, Any]] = []
    for u in payload.get("users", []) or []:
        if not u or not isinstance(u, dict):
            continue
        user = {k: v for k, v in u.items() if v not in (None, "")}
        if user.get("name"):
            users.append(user)
    if users:
        cfg["users"] = users

    # Packages
    packages = _ensure_list(payload.get("packages"))
    if packages:
        cfg["packages"] = packages

    # Package ops
    if payload.get("package_update") is not None:
        cfg["package_update"] = bool(payload.get("package_update"))
    if payload.get("package_upgrade") is not None:
        cfg["package_upgrade"] = bool(payload.get("package_upgrade"))

    # Write files
    write_files = []
    for wf in payload.get("write_files", []) or []:
        if not wf or not isinstance(wf, dict):
            continue
        if not wf.get("path"):
            continue
        entry = {k: v for k, v in wf.items() if v not in (None, "")}
        write_files.append(entry)
    if write_files:
        cfg["write_files"] = write_files

    # runcmd
    runcmd = _ensure_list(payload.get("runcmd"))
    if runcmd:
        cfg["runcmd"] = runcmd

    # SSH and root options
    if payload.get("ssh_pwauth") is not None:
        cfg["ssh_pwauth"] = bool(payload.get("ssh_pwauth"))
    if payload.get("disable_root") is not None:
        cfg["disable_root"] = bool(payload.get("disable_root"))

    # apt settings and sources
    apt_cfg: Dict[str, Any] = {}
    if payload.get("apt") and isinstance(payload.get("apt"), dict):
        apt_cfg.update({k: v for k, v in payload["apt"].items() if v is not None})

    apt_sources = payload.get("apt_sources") or []
    if apt_sources:
        sources_map: Dict[str, Any] = {}
        for idx, src in enumerate(apt_sources):
            if isinstance(src, dict):
                source_value = src.get("source") or src.get("deb")
                keyid = src.get("keyid")
                keyserver = src.get("keyserver")
                if source_value:
                    entry = {"source": source_value}
                    if keyid:
                        entry["keyid"] = keyid
                    if keyserver:
                        entry["keyserver"] = keyserver
                    sources_map[f"custom{idx+1}"] = entry
            elif isinstance(src, str):
                sources_map[f"custom{idx+1}"] = {"source": src}
        if sources_map:
            apt_cfg["sources"] = sources_map

    if apt_cfg:
        cfg["apt"] = apt_cfg

    # Final YAML
    yaml_str = yaml.safe_dump(cfg, sort_keys=False).rstrip() + "\n"
    return "#cloud-config\n" + yaml_str

