import io
from typing import Iterable
import os
import fnmatch


def iter_python_files(root: str) -> Iterable[str]:
    for base, dirs, files in os.walk(root):
        # prune heavy dirs
        skip = {".git", ".hg", ".svn", "__pycache__", "node_modules", "dist", "build", "site-packages", "venv", ".venv", "env"}
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(base, f)


def read_file_safely(path: str) -> str:
    # Try utf-8, fallback to latin-1
    try:
        with io.open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except UnicodeDecodeError:
        with io.open(path, "r", encoding="latin-1", errors="ignore") as fh:
            return fh.read()


def get_snippet(code: str, line: int, context: int = 2) -> str:
    if not line or line <= 0:
        return None
    lines = code.splitlines()
    start = max(1, line - context)
    end = min(len(lines), line + context)
    snippet = []
    for idx in range(start, end + 1):
        prefix = "> " if idx == line else "  "
        text = lines[idx - 1]
        snippet.append(f"{prefix}{idx:4d}: {text}")
    return "\n".join(snippet)

