import json
from typing import Any, Dict


def pretty_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def validate_manifest_text(text: str) -> Dict[str, Any]:
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object")

    if "project" not in manifest or not isinstance(manifest["project"], dict):
        raise ValueError("Manifest missing 'project' object")

    if "name" not in manifest["project"] or not manifest["project"]["name"]:
        raise ValueError("Manifest 'project' must include non-empty 'name'")

    # Normalize optional keys
    manifest.setdefault("pages", [])
    manifest.setdefault("models", [])
    manifest.setdefault("apis", [])

    if not isinstance(manifest["pages"], list):
        raise ValueError("'pages' must be an array")
    if not isinstance(manifest["models"], list):
        raise ValueError("'models' must be an array")
    if not isinstance(manifest["apis"], list):
        raise ValueError("'apis' must be an array")

    return manifest

