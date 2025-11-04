import os
import json
from typing import Dict, List, Optional


def get_storage_dir() -> str:
    base = os.environ.get("STORAGE_DIR", os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def get_release_dir(version: str) -> str:
    safe_version = version.replace("/", "_")
    return os.path.join(get_storage_dir(), "releases", safe_version)


def _manifest_path(version: str) -> str:
    return os.path.join(get_release_dir(version), "release.json")


def load_manifest(version: str) -> Optional[Dict]:
    path = _manifest_path(version)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(version: str, manifest: Dict) -> None:
    path = _manifest_path(version)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def list_releases() -> List[Dict]:
    releases_dir = os.path.join(get_storage_dir(), "releases")
    if not os.path.isdir(releases_dir):
        return []
    entries = []
    for name in sorted(os.listdir(releases_dir)):
        rel_dir = os.path.join(releases_dir, name)
        if not os.path.isdir(rel_dir):
            continue
        manifest_path = os.path.join(rel_dir, "release.json")
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                entries.append({
                    "version": manifest.get("version", name),
                    "createdAt": manifest.get("createdAt"),
                    "artifactCount": len(manifest.get("artifacts", [])),
                    "hasSbom": bool(manifest.get("sbom")),
                })
            except Exception:
                entries.append({"version": name, "error": "invalid manifest"})
        else:
            entries.append({"version": name, "error": "missing manifest"})
    return entries

