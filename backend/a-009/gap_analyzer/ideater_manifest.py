from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import json
import os

_ALLOWED_STATUSES = {"planned", "in-progress", "implemented", "deprecated"}


def normalize_status(value: Optional[str]) -> str:
    if not value:
        return "planned"
    v = str(value).strip().lower()
    v = v.replace("in progress", "in-progress")
    v = v.replace("in_progress", "in-progress")
    if v not in _ALLOWED_STATUSES:
        # Map common synonyms
        synonyms = {
            "todo": "planned",
            "tbd": "planned",
            "wip": "in-progress",
            "partial": "in-progress",
            "done": "implemented",
            "complete": "implemented",
            "completed": "implemented",
            "retired": "deprecated",
            "obsolete": "deprecated",
        }
        v = synonyms.get(v, "planned")
    return v


@dataclass
class Idea:
    id: str
    title: str
    status: str = "planned"
    tags: List[str] = field(default_factory=list)
    acceptance: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Manifest:
    version: str = "1.0"
    ideas: List[Idea] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


def _coerce_idea(raw: Dict[str, Any]) -> Tuple[Optional[Idea], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "Idea entry must be an object"
    # Allow alternate keys
    id_ = raw.get("id") or raw.get("key") or raw.get("slug")
    title = raw.get("title") or raw.get("name") or id_
    if not id_:
        return None, "Idea is missing required 'id'"
    if not title:
        return None, f"Idea '{id_}' missing 'title'"
    status = normalize_status(raw.get("status"))
    tags = list(raw.get("tags", []) or [])
    acceptance = list(raw.get("acceptance", []) or [])
    meta = dict(raw.get("meta", {}) or {})
    return Idea(id=id_, title=title, status=status, tags=tags, acceptance=acceptance, meta=meta), None


def load_manifest_from_dict(obj: Dict[str, Any]) -> Tuple[Manifest, List[str]]:
    warnings: List[str] = []
    if not isinstance(obj, dict):
        raise ValueError("Manifest must be a JSON object")

    # Support 'ideas' or legacy 'features'
    ideas_raw = obj.get("ideas")
    if ideas_raw is None:
        ideas_raw = obj.get("features")
        if ideas_raw is not None:
            warnings.append("Using legacy key 'features'; prefer 'ideas'")
    ideas: List[Idea] = []

    if not isinstance(ideas_raw, list):
        ideas_raw = []
        warnings.append("No 'ideas' array found in manifest; defaulting to empty")

    seen: set = set()
    for entry in ideas_raw:
        idea, err = _coerce_idea(entry)
        if err:
            warnings.append(err)
            continue
        if idea.id in seen:
            warnings.append(f"Duplicate idea id '{idea.id}' encountered; keeping first occurrence")
            continue
        seen.add(idea.id)
        ideas.append(idea)

    version = str(obj.get("version") or "1.0")
    meta = dict(obj.get("meta", {}) or {})
    return Manifest(version=version, ideas=ideas, meta=meta), warnings


def load_manifest_from_path(path: str) -> Tuple[Manifest, List[str]]:
    _, ext = os.path.splitext(path.lower())
    if ext in (".json", ""):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return load_manifest_from_dict(data)
    # Minimal YAML support if available
    if ext in (".yml", ".yaml"):
        try:
            import yaml  # type: ignore
        except Exception as e:
            raise RuntimeError("PyYAML is required to load YAML manifests") from e
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return load_manifest_from_dict(data)
    raise ValueError(f"Unsupported manifest file extension: {ext}")

