import re
from datetime import datetime


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "app"


def safe_package(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text.replace("-", "_"))
    if not text or not re.match(r"^[a-z_]", text):
        text = f"pkg_{text}"
    return text


def pluralize(word: str) -> str:
    w = word.strip().lower()
    if not w:
        return "items"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    if w.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    return w + "s"


def compute_context(payload: dict) -> dict:
    app_name = payload.get("app_name") or "MyApp"
    description = payload.get("description") or "App-specific Kubernetes operator"
    author_name = payload.get("author_name") or "Example Author"
    author_email = payload.get("author_email") or "author@example.com"
    license_spdx = payload.get("license") or "MIT"
    group = payload.get("group") or "apps.example.com"
    version = payload.get("version") or "v1alpha1"
    kind = payload.get("kind") or "App"
    kind_lower = kind.lower()
    plural = payload.get("plural") or pluralize(kind_lower)
    project_slug = payload.get("project_slug") or f"{slugify(app_name)}-operator"
    package_name = payload.get("package_name") or safe_package(f"{slugify(app_name)}_operator")
    python_version = payload.get("python_version") or "3.11"
    include_examples = payload.get("include_examples")
    if include_examples is None:
        include_examples = True
    operations = payload.get("operations") or ["reconcile", "scale", "backup"]
    image = payload.get("image") or f"ghcr.io/your-org/{project_slug}:latest"
    year = str(datetime.utcnow().year)

    return {
        "app_name": app_name,
        "description": description,
        "author_name": author_name,
        "author_email": author_email,
        "license": license_spdx,
        "group": group,
        "version": version,
        "kind": kind,
        "kind_lower": kind_lower,
        "plural": plural,
        "project_slug": project_slug,
        "package_name": package_name,
        "python_version": python_version,
        "include_examples": include_examples,
        "operations": operations,
        "image": image,
        "year": year,
    }

