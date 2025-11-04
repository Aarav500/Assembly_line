import os
import re
import json
from glob import glob
from typing import Dict, List, Optional, Tuple, Iterable

try:
    import tomllib  # Python 3.11+
    def load_toml(text: str) -> dict:
        return tomllib.loads(text)
except ModuleNotFoundError:  # pragma: no cover
    import tomli
    def load_toml(text: str) -> dict:
        return tomli.loads(text)

EXCLUDED_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".idea", ".vscode"}


def read_text(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        try:
            with open(path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception:
            return None


def safe_json_load(path: str) -> Optional[dict]:
    txt = read_text(path)
    if txt is None:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None


def find_files(root: str, patterns: Iterable[str]) -> List[str]:
    paths: List[str] = []
    for pattern in patterns:
        glob_pattern = os.path.join(root, pattern)
        paths.extend(glob(glob_pattern, recursive=True))
    # filter excluded directories
    filtered = []
    for p in paths:
        parts = set(os.path.normpath(p).split(os.sep))
        if EXCLUDED_DIRS.isdisjoint(parts):
            filtered.append(p)
    return sorted(set(filtered))


def parse_requirements_text(text: str) -> Dict[str, str]:
    deps: Dict[str, str] = {}
    if not text:
        return deps
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # remove inline comments
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        # skip vcs or -e installs but capture package name if possible
        if line.startswith(('-e', 'git+', 'hg+', 'svn+')):
            name = os.path.basename(line).split('.')[0]
            if name:
                deps[name] = line
            continue
        # simple splits for pkg and version specifier
        m = re.match(r"([A-Za-z0-9_.\-]+)\s*(.*)$", line)
        if m:
            name = m.group(1)
            spec = m.group(2).strip()
            if spec.startswith("@"):
                # PEP 508 direct URL
                deps[name] = spec
            elif spec:
                deps[name] = spec
            else:
                deps[name] = "*"
    return deps


def detect_python_imports(root: str, max_files: int = 500) -> List[str]:
    imports = set()
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(dirpath, fn)
            text = read_text(path)
            if not text:
                continue
            for line in text.splitlines()[:400]:
                line = line.strip()
                if line.startswith('import '):
                    parts = line.replace('import ', '').split(',')
                    for p in parts:
                        mod = p.strip().split(' ')[0].split('.')[0]
                        if mod:
                            imports.add(mod)
                elif line.startswith('from '):
                    mod = line.replace('from ', '').split(' import ')[0].split('.')[0].strip()
                    if mod:
                        imports.add(mod)
            count += 1
            if count >= max_files:
                break
        if count >= max_files:
            break
    return sorted(imports)


def guess_flask_port_from_code(root: str) -> Optional[int]:
    pattern = re.compile(r"app\.run\(.*?port\s*=\s*(\d+)", re.IGNORECASE | re.DOTALL)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            text = read_text(os.path.join(dirpath, fn))
            if not text:
                continue
            m = pattern.search(text)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
    return None


def find_flask_entrypoint(root: str) -> Optional[str]:
    # Prefer files that instantiate Flask and guard __main__
    inst_pattern = re.compile(r"\bFlask\s*\(")
    main_guard = re.compile(r"if __name__ == ['\"]__main__['\"]:")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dirpath, fn)
            text = read_text(p)
            if not text:
                continue
            if 'Flask(' in text and main_guard.search(text):
                rel = os.path.relpath(p, root)
                return rel.replace('\\', '/')
    # Fallback: app.py or main.py if they mention Flask
    for candidate in ("app.py", "main.py", os.path.join("src", "app.py")):
        p = os.path.join(root, candidate)
        if os.path.exists(p):
            t = read_text(p) or ''
            if 'Flask(' in t or 'from flask' in t:
                return os.path.relpath(p, root).replace('\\', '/')
    return None


def clean_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "", name)

