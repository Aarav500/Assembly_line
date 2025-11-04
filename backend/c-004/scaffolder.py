import io
import os
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

TEMPLATE_ROOT = Path(__file__).parent / "templates"

FRAMEWORKS = {
    "vite-react": "vite-react",
    "nextjs": "nextjs",
    "svelte": "svelte",
    "angular": "angular",
}

FRAMEWORK_INFO = [
    {"id": "vite-react", "label": "Vite + React", "path": str(TEMPLATE_ROOT / "vite-react")},
    {"id": "nextjs", "label": "Next.js", "path": str(TEMPLATE_ROOT / "nextjs")},
    {"id": "svelte", "label": "Svelte (Vite)", "path": str(TEMPLATE_ROOT / "svelte")},
    {"id": "angular", "label": "Angular", "path": str(TEMPLATE_ROOT / "angular")},
]

def list_frameworks() -> List[Dict[str, str]]:
    return [{"id": f["id"], "label": f["label"]} for f in FRAMEWORK_INFO]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "app"


def generate_zip(framework: str, app_name: str, app_description: str = "") -> Tuple[bytes, str]:
    key = framework.lower()
    if key not in FRAMEWORKS:
        raise KeyError(f"Unsupported framework: {framework}")
    tpl_path = TEMPLATE_ROOT / FRAMEWORKS[key]
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found for framework: {framework}")

    app_slug = slugify(app_name)
    placeholders: Dict[str, str] = {
        "__APP_NAME__": app_name,
        "__APP_SLUG__": app_slug,
        "__APP_DESCRIPTION__": app_description or f"{app_name} scaffold",
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(tpl_path):
            rel_root = os.path.relpath(root, tpl_path)
            for fname in files:
                src = Path(root) / fname
                rel_dir = "" if rel_root == "." else f"{rel_root}/"
                out_path = f"{app_slug}/{rel_dir}{fname}"
                data = src.read_bytes()
                try:
                    text = data.decode("utf-8")
                    for k, v in placeholders.items():
                        text = text.replace(k, v)
                    zf.writestr(out_path, text.encode("utf-8"))
                except UnicodeDecodeError:
                    # Binary file passthrough
                    zf.writestr(out_path, data)
    buf.seek(0)
    return buf.getvalue(), app_slug

