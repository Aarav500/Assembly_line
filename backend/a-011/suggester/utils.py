import os
import re
from typing import Iterable, Set

IGNORED_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache"}


def iter_files(root: str, exts: Iterable[str] | None = None):
    exts = set(exts or [])
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
        for fname in filenames:
            if exts:
                for ext in exts:
                    if fname.endswith(ext):
                        yield os.path.join(dirpath, fname)
                        break
            else:
                yield os.path.join(dirpath, fname)


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def slugify(s: str) -> str:
    s = s.strip().lower()
    # Replace path spaces and slashes meaningfully, preserve leading method if present
    s = re.sub(r"\s+", "-", s)
    s = s.replace("/", "-")
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def best_name(candidates: Iterable[str]) -> str:
    for c in candidates:
        c = (c or "").strip()
        if c:
            return c
    return "unknown"


def unique_by_slug(items: list[dict], key: str = "slug") -> list[dict]:
    seen: Set[str] = set()
    out: list[dict] = []
    for it in items:
        slug = it.get(key)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append(it)
    return out


def guess_test_dirs(root: str) -> list[str]:
    candidates = [
        os.path.join(root, "tests", "acceptance"),
        os.path.join(root, "tests", "e2e"),
        os.path.join(root, "tests", "system"),
        os.path.join(root, "acceptance"),
        os.path.join(root, "e2e"),
        os.path.join(root, "system"),
        os.path.join(root, "tests"),
        os.path.join(root, "test"),
    ]
    return [p for p in candidates if os.path.isdir(p)]


def priority_from_criticality(crit: str | None) -> str:
    if not crit:
        return "medium"
    c = crit.lower()
    if c in {"blocker", "critical", "high", "p0", "p1"}:
        return "high"
    if c in {"medium", "normal", "p2"}:
        return "medium"
    return "low"

