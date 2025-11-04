import os
from typing import Iterable

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache", ".idea", ".vscode", "build", "dist", "migrations"}


def iter_py_files(root: str, include_tests: bool = False):
    base = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(base):
        # prune unwanted directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]
        if not include_tests:
            dirnames[:] = [d for d in dirnames if d.lower() not in {"tests", "test"}]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            if not include_tests and (fn.startswith("test_") or fn.endswith("_test.py")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, base)
            yield full, rel


def top_level_packages(root: str):
    base = os.path.abspath(root)
    pkgs = set()
    for entry in os.listdir(base):
        if entry.startswith('.'):
            continue
        full = os.path.join(base, entry)
        if os.path.isdir(full):
            # treat as package if contains __init__.py or has any .py files
            if os.path.exists(os.path.join(full, "__init__.py")):
                pkgs.add(entry)
            else:
                for _p, _r, files in os.walk(full):
                    if any(f.endswith('.py') for f in files):
                        pkgs.add(entry)
                        break
        elif entry.endswith('.py'):
            name = os.path.splitext(entry)[0]
            pkgs.add(name)
    return pkgs


def safe_div(n: float, d: float) -> float:
    return (n / d) if d else 0.0


def normalize_module_path(rel_path: str) -> str:
    # convert file path to dotted module path (approximation)
    if rel_path.endswith('.py'):
        rel_path = rel_path[:-3]
    return rel_path.replace(os.sep, ".")


def first_package_from_module(module_path: str) -> str:
    return module_path.split(".", 1)[0] if module_path else ""


def uniq(seq: Iterable):
    seen = set()
    for x in seq:
        if x not in seen:
            seen.add(x)
            yield x

