import re
from pathlib import Path
from typing import Dict, List


def _iter_py_files(root: Path):
    for p in root.rglob("*.py"):
        # skip virtual environment folders
        if any(part in {".venv", "venv", "env", "__pycache__", ".lifecycle", ".git"} for part in p.parts):
            continue
        yield p


ROUTE_DECORATOR_RE = re.compile(
    r"@(?:(?:\w+)\.)?route\(\s*[\'\"]([^\'\"]+)[\'\"](?:[^)]*?methods\s*=\s*\[([^\]]+)\])?",
    re.IGNORECASE,
)


def _extract_routes(code: str) -> List[Dict]:
    routes = []
    for m in ROUTE_DECORATOR_RE.finditer(code):
        path = m.group(1)
        methods_raw = m.group(2)
        methods = []
        if methods_raw:
            # parse '"GET", "POST"' style lists
            methods = [s.strip().strip("'\"") for s in methods_raw.split(",") if s.strip()]
        routes.append({"path": path, "methods": methods or ["GET"]})
    return routes


def analyze_project(root: Path) -> Dict:
    root = root.resolve()
    files = list(_iter_py_files(root))
    total_lines = 0
    func_defs = 0
    classes = 0
    routes = []
    for p in files:
        try:
            code = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        total_lines += len(code.splitlines())
        func_defs += code.count("def ")
        classes += code.count("class ")
        routes.extend(_extract_routes(code))

    return {
        "root": str(root),
        "files": len(files),
        "lines": total_lines,
        "functions": func_defs,
        "classes": classes,
        "routes": routes,
    }

