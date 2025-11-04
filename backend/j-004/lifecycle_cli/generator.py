from pathlib import Path
from jinja2 import Template
from .analysis import analyze_project

_DOCKERFILE_TEMPLATE = """
# syntax=docker/dockerfile:1
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install -r requirements.txt
COPY . /app
EXPOSE 8000
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8000"]
""".lstrip()


def generate_openapi_spec(root: Path) -> dict:
    """Generate a minimal OpenAPI-like spec from route decorators."""
    analysis = analyze_project(root)
    paths = {}
    for r in analysis.get("routes", []):
        path = r.get("path", "/")
        methods = r.get("methods") or ["GET"]
        path_item = {}
        for m in methods:
            op = m.lower()
            path_item[op] = {
                "summary": f"Auto-generated endpoint for {path}",
                "responses": {"200": {"description": "OK"}},
            }
        paths[path] = path_item
    return {
        "openapi": "3.0.0",
        "info": {"title": root.name, "version": "0.1.0"},
        "paths": paths,
    }


def generate_dockerfile(root: Path, overwrite: bool = False) -> Path:
    dockerfile = root / "Dockerfile"
    if dockerfile.exists() and not overwrite:
        raise FileExistsError(f"Dockerfile already exists: {dockerfile}. Use --force to overwrite.")
    # Ensure requirements.txt exists minimally
    req = root / "requirements.txt"
    if not req.exists():
        req.write_text("Flask>=2.3\n", encoding="utf-8")
    content = Template(_DOCKERFILE_TEMPLATE).render()
    dockerfile.write_text(content, encoding="utf-8")
    return dockerfile

