import os
import re
import json
import fnmatch
from typing import Dict, List, Set, Tuple, Any

try:  # Python 3.11+
    import tomllib as tomli  # type: ignore
except Exception:  # pragma: no cover
    import tomli  # type: ignore

import yaml

MAX_READ_BYTES = 524288  # 512 KiB
SKIP_DIRS = {
    ".git", "node_modules", "vendor", ".venv", "venv", "env", ".tox", "dist", "build", "target",
    "__pycache__", ".idea", ".vscode", ".terraform", ".next", ".nuxt", ".svelte-kit", ".pnpm-store",
    ".cache", "coverage", ".gradle", "out"
}

FRONTEND_FRAMEWORK_PATTERNS = {
    "react": ["react"],
    "next": ["next"],
    "vue": ["vue"],
    "nuxt": ["nuxt", "nuxt3"],
    "angular": ["@angular/core"],
    "svelte": ["svelte"],
    "sveltekit": ["@sveltejs/kit"],
    "gatsby": ["gatsby"],
    "astro": ["astro"],
    "preact": ["preact"],
    "solid": ["solid-js"],
    "remix": ["remix", "@remix-run/node", "@remix-run/react"],
    "ember": ["ember-source"],
}

FRONTEND_TOOLING = [
    "vite", "webpack", "rollup", "parcel", "esbuild", "gulp", "grunt", "snowpack", "vitepress", "docusaurus"
]

JS_BACKEND_FRAMEWORKS = {
    "express": ["express"],
    "koa": ["koa"],
    "hapi": ["@hapi/hapi", "hapi"],
    "fastify": ["fastify"],
    "nestjs": ["@nestjs/core"],
    "adonis": ["@adonisjs/core", "adonisjs"],
    "sails": ["sails"],
    "strapi": ["strapi"],
    "keystone": ["@keystone-6/core", "@keystonejs/keystone"],
    "loopback": ["@loopback/core", "loopback"],
    "feathers": ["@feathersjs/feathers", "feathers"],
    "meteor": ["meteor"],
}

PYTHON_FRAMEWORKS = [
    "flask", "django", "fastapi", "tornado", "sanic", "pyramid", "bottle", "falcon", "starlette", "aiohttp", "quart"
]

PACKAGE_MANAGERS_JS = {
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "package-lock.json": "npm",
}

PACKAGE_MANAGERS_PY = {
    "poetry": ["pyproject.toml"],
    "pipenv": ["Pipfile"],
    "pip": ["requirements.txt", "setup.py", "setup.cfg"],
    "uv": ["uv.lock"],
}

CICD_PATHS = {
    "github_actions": ".github/workflows",
    "circleci": ".circleci/config.yml",
    "gitlab_ci": ".gitlab-ci.yml",
    "azure_pipelines": "azure-pipelines.yml",
}

INFRA_FILENAMES = {
    "docker": ["Dockerfile", "docker-compose.simple.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"],
    "helm_chart": ["Chart.yaml"],
    "serverless": ["serverless.yml", "serverless.yaml"],
    "pulumi": ["Pulumi.yaml"],
    "skaffold": ["skaffold.yml", "skaffold.yaml"],
    "make": ["Makefile"],
}


def _norm(s: str) -> str:
    return s.strip().lower()


def safe_read_text(path: str, max_bytes: int = MAX_READ_BYTES) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def list_files(root: str) -> List[str]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            files.append(os.path.join(dirpath, fn))
    return files


def parse_requirements_lines(content: str) -> Set[str]:
    pkgs: Set[str] = set()
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # remove inline comments
        line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        # handle extras and version specifiers
        name = re.split(r"[<>=!~]", line, maxsplit=1)[0]
        name = name.split("[", 1)[0]
        name = name.strip().lower()
        if name:
            pkgs.add(name)
    return pkgs


def parse_pyproject(path: str) -> Set[str]:
    try:
        with open(path, "rb") as f:
            data = tomli.load(f)
    except Exception:
        return set()
    deps: Set[str] = set()
    # PEP 621
    project = data.get("project") or {}
    for d in project.get("dependencies", []) or []:
        name = re.split(r"[<>=!~]", str(d), maxsplit=1)[0]
        name = name.split("[", 1)[0]
        if name:
            deps.add(name.strip().lower())
    # Optional deps
    opt = project.get("optional-dependencies") or {}
    for group in opt.values():
        for d in group or []:
            name = re.split(r"[<>=!~]", str(d), maxsplit=1)[0]
            name = name.split("[", 1)[0]
            if name:
                deps.add(name.strip().lower())
    # Poetry
    poetry = (data.get("tool") or {}).get("poetry") or {}
    for section in ("dependencies", "dev-dependencies"):
        for name in (poetry.get(section) or {}).keys():
            if name and name != "python":
                deps.add(str(name).strip().lower())
    return deps


def parse_pipfile(path: str) -> Set[str]:
    # Pipfile is TOML-like
    try:
        with open(path, "rb") as f:
            data = tomli.load(f)
    except Exception:
        return set()
    deps: Set[str] = set()
    for section in ("packages", "dev-packages"):
        for name in (data.get(section) or {}).keys():
            if name:
                deps.add(str(name).strip().lower())
    return deps


def parse_package_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
    except Exception:
        return {}
    return pkg


def detect_python(root: str, files: List[str]) -> Tuple[bool, Dict[str, Any]]:
    py_files = [f for f in files if f.endswith(".py")]
    req_files = [f for f in files if os.path.basename(f) == "requirements.txt"]
    pyproject_files = [f for f in files if os.path.basename(f) == "pyproject.toml"]
    pipfile_files = [f for f in files if os.path.basename(f) == "Pipfile"]

    deps: Set[str] = set()
    for f in req_files:
        deps |= parse_requirements_lines(safe_read_text(f))
    for f in pyproject_files:
        deps |= parse_pyproject(f)
    for f in pipfile_files:
        deps |= parse_pipfile(f)

    frameworks_found: List[str] = []
    for fw in PYTHON_FRAMEWORKS:
        if fw in deps:
            frameworks_found.append(fw)
    # Heuristic: detect Flask/Django, etc. from source if deps not explicit
    if not frameworks_found and py_files:
        for f in py_files[:100]:  # limit reads
            txt = safe_read_text(f)
            if not txt:
                continue
            for fw in PYTHON_FRAMEWORKS:
                pattern = rf"\bimport\s+{re.escape(fw)}\b|\bfrom\s+{re.escape(fw)}\s+import\b"
                if re.search(pattern, txt):
                    if fw not in frameworks_found:
                        frameworks_found.append(fw)

    # Package manager
    pm_py = None
    for pm, markers in PACKAGE_MANAGERS_PY.items():
        for m in markers:
            if any(os.path.basename(f) == m for f in files):
                pm_py = pm
                break
        if pm_py:
            break

    present = bool(py_files or req_files or pyproject_files or pipfile_files)
    return present, {
        "language": "python",
        "frameworks": frameworks_found,
        "package_manager": pm_py,
        "evidence": {
            "requirements": req_files,
            "pyproject": pyproject_files,
            "pipfile": pipfile_files,
            "sources": py_files[:50],
        },
    }


def detect_js(root: str, files: List[str]) -> Tuple[bool, Dict[str, Any], List[Dict[str, Any]]]:
    pkg_files = [f for f in files if os.path.basename(f) == "package.json"]
    if not pkg_files:
        # still detect via lock files to get package manager
        js_pm = None
        for lock, pm in PACKAGE_MANAGERS_JS.items():
            if any(os.path.basename(f) == lock for f in files):
                js_pm = pm
                break
        return False, {"package_manager": js_pm}, []

    all_frontend = []
    backend_fw: List[str] = []
    tooling: Set[str] = set()
    js_pm = None

    # PM from lockfiles if present
    for lock, pm in PACKAGE_MANAGERS_JS.items():
        if any(os.path.basename(f) == lock for f in files):
            js_pm = pm
            break

    for pkg_path in pkg_files:
        pkg = parse_package_json(pkg_path)
        if not pkg:
            continue
        all_deps = {}
        all_deps.update(pkg.get("dependencies", {}) or {})
        all_deps.update(pkg.get("devDependencies", {}) or {})
        all_deps.update(pkg.get("peerDependencies", {}) or {})

        detected_frameworks: List[str] = []
        for fw_name, patterns in FRONTEND_FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if pattern in all_deps:
                    detected_frameworks.append(fw_name)
                    break

        detected_tooling: List[str] = []
        for tool in FRONTEND_TOOLING:
            if tool in all_deps:
                detected_tooling.append(tool)
                tooling.add(tool)

        for fw_name, patterns in JS_BACKEND_FRAMEWORKS.items():
            for pattern in patterns:
                if pattern in all_deps:
                    if fw_name not in backend_fw:
                        backend_fw.append(fw_name)
                    break

        if detected_frameworks:
            all_frontend.append({
                "frameworks": detected_frameworks,
                "tooling": detected_tooling,
                "package_json": pkg_path,
            })

    has_js = bool(pkg_files)
    backend_info = {
        "language": "javascript",
        "frameworks": backend_fw,
        "package_manager": js_pm,
    }
    return has_js, backend_info, all_frontend


def detect_infra(root: str, files: List[str]) -> Dict[str, List[str]]:
    infra: Dict[str, List[str]] = {}
    for infra_type, filenames in INFRA_FILENAMES.items():
        found = []
        for fn in filenames:
            matches = [f for f in files if os.path.basename(f) == fn]
            found.extend(matches)
        if found:
            infra[infra_type] = found

    # Terraform
    tf_files = [f for f in files if f.endswith(".tf")]
    if tf_files:
        infra["terraform"] = tf_files

    # Kubernetes
    k8s_files = []
    for f in files:
        if f.endswith((".yaml", ".yml")):
            txt = safe_read_text(f, max_bytes=8192)
            if "apiVersion:" in txt and "kind:" in txt:
                k8s_files.append(f)
    if k8s_files:
        infra["kubernetes"] = k8s_files

    return infra


def detect_cicd(root: str, files: List[str]) -> Dict[str, Any]:
    cicd: Dict[str, Any] = {}
    for name, path_pattern in CICD_PATHS.items():
        if "/" in path_pattern:
            # directory pattern
            if any(path_pattern in f for f in files):
                cicd[name] = True
        else:
            # file pattern
            if any(os.path.basename(f) == path_pattern for f in files):
                cicd[name] = True

    # Jenkins
    if any(os.path.basename(f) == "Jenkinsfile" for f in files):
        cicd["jenkins"] = True

    # Travis
    if any(os.path.basename(f) == ".travis.yml" for f in files):
        cicd["travis"] = True

    return cicd


def detect_project_types(root: str) -> Dict[str, Any]:
    files = list_files(root)

    result: Dict[str, Any] = {
        "backend": [],
        "frontend": [],
        "infrastructure": {},
        "cicd": {},
    }

    # Python
    py_present, py_info = detect_python(root, files)
    if py_present:
        result["backend"].append(py_info)

    # JavaScript/TypeScript
    js_present, js_backend_info, js_frontend = detect_js(root, files)
    if js_present:
        if js_backend_info.get("frameworks"):
            result["backend"].append(js_backend_info)
        if js_frontend:
            result["frontend"].extend(js_frontend)

    # Infrastructure
    result["infrastructure"] = detect_infra(root, files)

    # CI/CD
    result["cicd"] = detect_cicd(root, files)

    return result
