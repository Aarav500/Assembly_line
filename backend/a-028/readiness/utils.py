import os
import re
from typing import Dict, List, Optional, Any


def list_files(root: str) -> List[str]:
    files = []
    for base, _, filenames in os.walk(root):
        for f in filenames:
            files.append(os.path.join(base, f))
    return files


def has_any(root: str, names: List[str]) -> bool:
    for n in names:
        if os.path.exists(os.path.join(root, n)):
            return True
    return False


def glob_find(root: str, patterns: List[str]) -> List[str]:
    # Simple manual glob over all files
    import fnmatch
    matches: List[str] = []
    for path in list_files(root):
        rel = os.path.relpath(path, root)
        for p in patterns:
            if fnmatch.fnmatch(rel, p):
                matches.append(path)
                break
    return matches


def read_text_safe(path: str, max_bytes: int = 2_000_000) -> str:
    try:
        if os.path.getsize(path) > max_bytes:
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def count_python_files(root: str, exclude_dirs: Optional[List[str]] = None) -> int:
    if exclude_dirs is None:
        exclude_dirs = []
    count = 0
    for base, dirs, files in os.walk(root):
        # Exclude test and virtualenv and build dirs
        skip = False
        for ex in exclude_dirs:
            if os.path.abspath(base).startswith(os.path.abspath(os.path.join(root, ex))):
                skip = True
                break
        if skip:
            continue
        # prune common dirs
        dirs[:] = [d for d in dirs if d not in [".git", "venv", ".venv", "node_modules", "__pycache__", "dist", "build"]]
        for f in files:
            if f.endswith(".py"):
                count += 1
    return count


def parse_coverage_xml(content: str) -> Optional[float]:
    # Parse 'line-rate' from coverage.xml root <coverage line-rate="0.85" ....>
    if not content:
        return None
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
        rate = root.attrib.get("line-rate")
        if rate is None:
            return None
        pct = float(rate) * 100.0
        if pct < 0 or pct > 1000:
            return None
        return pct
    except Exception:
        return None


def parse_coverage_from_badges(text: str) -> Optional[float]:
    if not text:
        return None
    # Common badge patterns like: coverage-85%25, coverage-85% or shields.io alt text
    patterns = [
        r"coverage[-_](?P<pct>\d{1,3})%25",
        r"coverage[-_](?P<pct>\d{1,3})%",
        r"\bcoverage[^\n]*?(?P<pct>\d{1,3})%\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                pct = float(m.group("pct"))
                if 0 <= pct <= 100:
                    return pct
            except Exception:
                continue
    return None


def yaml_load_safe(text: str) -> Optional[Any]:
    if not text:
        return None
    try:
        import yaml
        return yaml.safe_load(text)
    except Exception:
        return None


def is_truthy(val: Optional[str]) -> bool:
    return str(val).lower() in {"1", "true", "yes", "on"}

