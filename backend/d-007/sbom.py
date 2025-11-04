import os
import re
import json
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from storage import get_release_dir, load_manifest


SPEC_VERSION = "1.5"


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _file_hashes(path: str) -> Dict[str, str]:
    algos = ["sha256", "sha512"]
    hashes = {}
    for algo in algos:
        h = hashlib.new(algo)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        hashes[algo] = h.hexdigest()
    return hashes


def _parse_requirements_text(text: str) -> List[Tuple[str, Optional[str]]]:
    comps: List[Tuple[str, Optional[str]]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Simple parser: package[extras]?==version | ~=version | >= | <= | = | ===
        # We only pin explicit versions when present; otherwise, version is None.
        m = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[.*\])?(?:\s*(==|===|~=|=|>=|<=)\s*([A-Za-z0-9_.\-]+))?", line)
        if not m:
            continue
        name = m.group(1)
        op = m.group(2)
        ver = m.group(3)
        if op in ("==", "===", "=", "~=") and ver:
            comps.append((name, ver))
        else:
            comps.append((name, None))
    return comps


def _read_requirements(release_dir: str) -> List[Tuple[str, Optional[str]]]:
    req_path = os.path.join(release_dir, "requirements.txt")
    if not os.path.isfile(req_path):
        return []
    with open(req_path, "r", encoding="utf-8") as f:
        return _parse_requirements_text(f.read())


def _artifact_components(release_dir: str, artifacts: List[Dict]) -> List[Dict]:
    comps: List[Dict] = []
    for art in artifacts:
        filename = art.get("filename") or art.get("path")
        if not filename:
            continue
        path = os.path.join(release_dir, filename)
        if not os.path.isfile(path):
            continue
        hashes = art.get("hashes") or _file_hashes(path)
        bom_ref = f"file:{filename}"
        comp = {
            "bom-ref": bom_ref,
            "type": "file",
            "name": filename,
            "version": art.get("uploadedAt") or "",
            "hashes": [
                {"alg": "SHA-256", "content": hashes.get("sha256", "")},
                {"alg": "SHA-512", "content": hashes.get("sha512", "")},
            ],
            "properties": [
                {"name": "cdx:artifact:filename", "value": filename},
                {"name": "cdx:artifact:size", "value": str(art.get("size", 0))},
                {"name": "cdx:artifact:contentType", "value": art.get("contentType", "")},
            ],
        }
        comps.append(comp)
    return comps


def _requirements_components(reqs: List[Tuple[str, Optional[str]]]) -> List[Dict]:
    comps: List[Dict] = []
    for name, version in reqs:
        name_norm = name.replace("_", "-").lower()
        purl = f"pkg:pypi/{name_norm}"
        bom_ref = purl if not version else f"{purl}@{version}"
        comp = {
            "bom-ref": bom_ref,
            "type": "library",
            "name": name_norm,
            **({"version": version} if version else {}),
            "purl": bom_ref if version else purl,
            "group": "pypi",
            "scope": "required",
        }
        comps.append(comp)
    return comps


def _build_bom(version: str, artifacts: List[Dict], reqs: List[Tuple[str, Optional[str]]]) -> Dict:
    release_dir = get_release_dir(version)

    root_ref = f"release:{version}"
    components: List[Dict] = []

    # Root application component
    root_component = {
        "bom-ref": root_ref,
        "type": "application",
        "name": "release",
        "version": version,
        "properties": [
            {"name": "cdx:release:version", "value": version},
            {"name": "cdx:release:dir", "value": release_dir},
        ],
    }

    file_components = _artifact_components(release_dir, artifacts)
    dep_components = _requirements_components(reqs)

    components.extend([root_component])
    components.extend(file_components)
    components.extend(dep_components)

    # Dependencies: root depends on everything else
    depends_on = [c["bom-ref"] for c in file_components + dep_components]
    dependencies = [{"ref": root_ref, "dependsOn": depends_on}] if depends_on else []

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": SPEC_VERSION,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": _now_iso(),
            "tools": [
                {
                    "vendor": "example",
                    "name": "sbom-generation-service",
                    "version": "1.0.0",
                }
            ],
            "component": root_component,
        },
        "components": components,
        "dependencies": dependencies,
    }

    return bom


def generate_sbom_for_release(version: str) -> (str, Dict):
    manifest = load_manifest(version)
    if not manifest:
        raise FileNotFoundError(f"release '{version}' not found")

    release_dir = get_release_dir(version)
    reqs = _read_requirements(release_dir)
    artifacts = manifest.get("artifacts", [])

    bom = _build_bom(version, artifacts, reqs)

    out_path = os.path.join(release_dir, "sbom.cdx.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bom, f, indent=2)

    return out_path, bom

